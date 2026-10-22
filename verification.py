"""Conservative transpilation checks, independent of the existing analyser.

PASS is scoped to the constraints/method reported; no backend is selected by
the current UI. Limits bound matrix allocation before constructing operators.
"""
from dataclasses import dataclass

import numpy as np
from qiskit.circuit import Gate
from qiskit.circuit.library import HGate
from qiskit.quantum_info import Operator

from transpile import resolve_basis_gates


@dataclass(frozen=True)
class VerificationLimits:
    max_qubits: int = 8
    max_instructions: int = 2000
    max_output_bits: int = 8
    atol: float = 1e-8
    rtol: float = 1e-7
    max_matrix_display_qubits: int = 3


def selected_constraints(basis_choice, custom_basis_gates=None):
    return {"basis_gates": resolve_basis_gates(basis_choice, custom_basis_gates)}


def check_transpilation_necessity(circuit, target_constraints=None, optimization_requested=False):
    """Priority: unsupported, known violations, unknowns, optional, compatible.

    Optional constraints: Qiskit Target, basis_gates, coupling_map, num_qubits,
    supported_operations. Physical indices are the circuit's current indices.
    """
    c = target_constraints or {}
    target = c.get("target")
    basis = set(target.operation_names) if target is not None else c.get("basis_gates")
    capacity = target.num_qubits if target is not None else c.get("num_qubits")
    coupling = c.get("coupling_map")
    edges = set(map(tuple, coupling.get_edges() if hasattr(coupling, "get_edges") else coupling or []))
    scope = "physical instruction constraints" if target is not None else "configured constraints only"
    violations, unknown, unsupported = [], [], []
    limitations = []
    if target is None:
        limitations.append("No physical backend selected: basis compatibility does not establish hardware compatibility.")
    else:
        limitations.append("Instruction support checked; pulse timing, calibration and execution fidelity are not verified.")
    if capacity is not None and circuit.num_qubits > capacity:
        unsupported.append(f"Circuit needs {circuit.num_qubits} qubits; target has {capacity}. Transpilation cannot supply extra hardware qubits.")
        violations.append({"kind": "capacity", "reason": unsupported[-1]})
    if basis is None and target is None:
        unknown.append("No execution target was specified, so hardware transpilation necessity cannot be determined. General circuit optimization can still be performed.")
    if circuit.parameters:
        unsupported.append("Bind circuit parameters before reliable target analysis and verification.")
    for item in circuit.data:
        op = item.operation
        name = op.name
        qubits = tuple(circuit.find_bit(q).index for q in item.qubits)
        if name == "barrier":
            continue  # compiler directive, not a physical instruction
        if getattr(op, "condition", None) is not None or hasattr(op, "blocks"):
            unsupported.append("Dynamic control flow and classical conditions are not supported by this checker.")
            continue
        if target is not None:
            if not target.instruction_supported(operation_name=name, qargs=qubits, parameters=list(op.params)):
                violations.append({"kind": "instruction_support", "operation": name, "qubits": qubits,
                                   "reason": f"{name} is not supported on physical qubits {qubits} with these parameters."})
        elif isinstance(op, Gate):
            if basis is not None and name not in basis:
                violations.append({"kind": "basis", "operation": name, "qubits": qubits,
                                   "reason": f"{name} is outside the selected basis and requires decomposition or replacement."})
        elif name in ("measure", "reset", "delay"):
            supported = c.get("supported_operations")
            if supported is None:
                unknown.append(f"The basis-only configuration does not specify support for {name}.")
            elif name not in supported:
                unsupported.append(f"Target does not support {name}; reliable conversion is not established.")
        else:
            unsupported.append(f"Instruction {name} is outside the supported necessity analysis.")
        if coupling is not None and len(qubits) == 2 and qubits not in edges:
            # Symmetric gates can use either direction; CX and unknown gates cannot.
            if not (name in ("cz", "swap", "rzz", "rxx", "ryy") and qubits[::-1] in edges):
                violations.append({"kind": "connectivity", "operation": name, "qubits": qubits,
                                   "reason": f"{name}{qubits} violates directed coupling constraints on the current mapping."})
        elif coupling is not None and len(qubits) > 2:
            unknown.append("Coupling-only checks cannot establish support for operations on more than two qubits.")
    status = ("UNSUPPORTED" if unsupported else "REQUIRED" if violations else
              "UNDETERMINED" if unknown else "OPTIONAL" if optimization_requested else "NOT_REQUIRED")
    reasons = list(dict.fromkeys(unsupported + [v["reason"] for v in violations] + unknown))
    if not reasons:
        reasons = ["All applicable configured constraints are satisfied." +
                   (" Optimization was requested, so transpilation is optional." if optimization_requested else "")]
    return {"status": status, "reasons": reasons, "violations": violations,
            "unknowns": list(dict.fromkeys(unknown)), "scope": scope, "limitations": limitations}


def verify_target_compatibility(circuit, constraints=None):
    result = check_transpilation_necessity(circuit, constraints)
    result["status"] = ("FAIL" if result["violations"] else "PASS"
                        if result["status"] in ("NOT_REQUIRED", "OPTIONAL") else "INCONCLUSIVE")
    return result


def _unitary_prefix(circuit):
    """Strip only a strictly terminal measurement suffix, retaining its mapping."""
    prefix = circuit.copy_empty_like()
    prefix.global_phase = circuit.global_phase
    measurements = []
    for item in circuit.data:
        op = item.operation
        if op.name == "barrier":
            continue
        if op.name == "measure":
            measurements.append((circuit.find_bit(item.qubits[0]).index,
                                 circuit.find_bit(item.clbits[0]).index))
            continue
        if measurements:
            raise ValueError("Intermediate measurements are not supported.")
        if not isinstance(op, Gate) or getattr(op, "condition", None) is not None:
            raise ValueError(f"Non-unitary, custom instruction or classical control ({op.name}) is unsupported.")
        prefix.append(op, item.qubits, item.clbits)
    return prefix, measurements


def _probabilities(matrix, mapping, bits):
    values = np.abs(matrix[:, 0]) ** 2
    if not mapping:
        return values
    result = np.zeros(2 ** bits)
    for state, probability in enumerate(values):
        outcome = 0
        for qubit, bit in mapping:
            outcome = (outcome & ~(1 << bit)) | (((state >> qubit) & 1) << bit)
        result[outcome] += probability
    return result


def verify_functional_equivalence(original, transpiled, limits=None):
    limits = limits or VerificationLimits()
    result = {"status": "INCONCLUSIVE", "method": "none", "universal": False,
              "reasons": [], "limitations": [], "output_comparison": None,
              "atol": limits.atol, "rtol": limits.rtol,
              "matrices": None, "matrix_dimension": None,
              "matrix_message": "Matrices unavailable because unitary verification has not completed.",
              "equivalent": None, "global_phase_radians": None,
              "phase_aligned_max_difference": None}
    def stop(status, reason):
        result.update(status=status, reasons=[reason], equivalent=None)
        return result
    if max(original.num_qubits, transpiled.num_qubits) > limits.max_qubits or max(len(original.data), len(transpiled.data)) > limits.max_instructions:
        return stop("INCONCLUSIVE", f"Exact verification limit exceeded ({limits.max_qubits} qubits, {limits.max_instructions} instructions).")
    if original.num_qubits != transpiled.num_qubits:
        return stop("INCONCLUSIVE", "Added ancillas or unequal circuit widths require an isometry comparison, which is not implemented.")
    if original.parameters or transpiled.parameters:
        return stop("INCONCLUSIVE", "Bind all parameters before numerical verification.")
    try:
        a, am = _unitary_prefix(original)
        b, bm = _unitary_prefix(transpiled)
    except ValueError as exc:
        return stop("UNSUPPORTED", str(exc))
    measured = bool(am or bm)
    if bool(am) != bool(bm) or original.num_clbits != transpiled.num_clbits:
        return stop("INCONCLUSIVE", "Measurement or classical interfaces differ; supported comparison cannot establish equivalence.")
    if measured and (original.layout is not None or transpiled.layout is not None):
        return stop("INCONCLUSIVE", "Measurement comparison with physical layout metadata is not implemented.")
    try:
        # Use the original circuits for layout metadata. Operator.from_circuit
        # restores logical input/output ordering for equal-width unitary circuits.
        ao = Operator(a) if measured else Operator.from_circuit(original)
        bo = Operator(b) if measured else Operator.from_circuit(transpiled)
        if not ao.is_unitary(atol=limits.atol, rtol=limits.rtol) or not bo.is_unitary(atol=limits.atol, rtol=limits.rtol):
            return stop("UNSUPPORTED", "Circuit prefix does not define a unitary operator.")
        equivalent = ao.equiv(bo, atol=limits.atol, rtol=limits.rtol)
        if not measured:
            result["equivalent"] = bool(equivalent)
            result["matrix_dimension"] = int(ao.data.shape[0])
            # For A = exp(i phi) B, the Hilbert-Schmidt overlap gives phi.
            # A phase is reported only when equiv() establishes equivalence.
            overlap = np.vdot(bo.data, ao.data)
            if equivalent and abs(overlap) > limits.atol:
                phase = float(np.angle(overlap))
                result["global_phase_radians"] = phase
                result["phase_aligned_max_difference"] = float(np.max(np.abs(ao.data - np.exp(1j * phase) * bo.data)))
            if original.num_qubits <= min(limits.max_matrix_display_qubits, 4):
                def display_number(value):
                    real, imag = round(float(value.real), 4), round(float(value.imag), 4)
                    if not imag:
                        return f"{real:g}" if real else "0"
                    if not real:
                        return f"{imag:g}i"
                    return f"{real:g} {'+' if imag >= 0 else '-'} {abs(imag):g}i"
                result["matrices"] = {
                    "original": [[display_number(x) for x in row] for row in ao.data],
                    "transpiled": [[display_number(x) for x in row] for row in bo.data],
                    "decimals": 4,
                    "ordering": "Logical computational basis, |00...0> through |11...1>; highest qubit index on the left. Columns are inputs, rows are outputs."}
                result["matrix_message"] = "Matrices include global phase and are rounded for display only. Verification uses unrounded values."
            else:
                result["matrix_message"] = "Matrix visualization is unavailable for this circuit size. Mathematical verification status is shown separately."
        else:
            result["matrix_message"] = "A measured circuit has no complete unitary matrix. Terminal measurements use a separate prefix-and-mapping verification method."
        bits = original.num_clbits if measured else original.num_qubits
        if bits <= limits.max_output_bits:
            ap = _probabilities(ao.data, am, bits)
            bp = _probabilities(bo.data, bm, bits)
            result["output_comparison"] = {
                "input": "All qubits initialized to |0>; classical bits initially zero.",
                "ordering": "Classical bits highest index to lowest (register separators omitted)." if measured else "Logical qubits highest index to lowest.",
                "rows": [{"state": format(i, f"0{bits}b"), "original": float(x), "transpiled": float(y)} for i, (x, y) in enumerate(zip(ap, bp))],
                "max_difference": float(np.max(np.abs(ap - bp))),
                "matches": bool(np.allclose(ap, bp, atol=limits.atol, rtol=limits.rtol))}
        else:
            result["limitations"].append("Output table omitted because the configured output-bit limit was exceeded.")
        if not measured:
            result.update(status="PASS" if equivalent else "FAIL", method="unitary_operator_equivalence", universal=True)
            result["reasons"] = ["Both circuits implement the same logical unitary operation up to global phase for all inputs, within numerical tolerances." if equivalent else "The logical unitary operators are not equivalent up to global phase within the configured tolerances."]
        # Measurements on separate classical destinations commute. Preserve
        # write order within each destination (including repeated writes).
        elif equivalent and sorted(am, key=lambda pair: pair[1]) == sorted(bm, key=lambda pair: pair[1]):
            result.update(status="PASS", method="unitary_prefix_and_identical_terminal_measurements", universal=True)
            result["reasons"] = ["Unitary prefixes agree up to global phase and qubit-to-classical-bit measurements agree, including write order for each classical bit; this establishes the same measured computation for all inputs."]
        else:
            result.update(method="exact_zero_input_measurement_probabilities")
            output = result["output_comparison"]
            result["status"] = "FAIL" if output is not None and not output["matches"] else "INCONCLUSIVE"
            result["reasons"] = ["Different exact zero-input distributions disprove equivalence." if result["status"] == "FAIL" else "Matching selected-input probabilities do not prove equivalence for all inputs."]
        result["limitations"].append("Exact matrix calculation with floating-point tolerances, not symbolic proof. Output probabilities illustrate only the zero input; no noise model is included.")
        return result
    except Exception as exc:
        return stop("ERROR", f"Operator verification could not complete: {exc}")


def compare_circuit_metrics(original, transpiled):
    def metrics(qc):
        gates = [item for item in qc.data if isinstance(item.operation, Gate)]
        return {"qubits": qc.num_qubits, "operations": qc.size(), "depth": qc.depth(),
                "single_qubit_gates": sum(len(i.qubits) == 1 for i in gates),
                "multi_qubit_gates": sum(len(i.qubits) > 1 for i in gates),
                "gate_counts": dict(qc.count_ops())}
    before, after = metrics(original), metrics(transpiled)
    added = sorted(set(after["gate_counts"]) - set(before["gate_counts"]))
    removed = sorted(set(before["gate_counts"]) - set(after["gate_counts"]))
    return {"original": before, "transpiled": after, "added": added, "removed": removed,
            "explanation": "Gate representation changed during transpilation. Functional equivalence was checked separately. Count changes alone do not identify individual cancellations or replacements."}


def generate_verification_report(original, transpiled, constraints, necessity, limits=None, error=None):
    report = {"necessity": necessity, "transpilation": {"status": "ERROR" if error else "SUCCESS"},
              "target_compatibility": {"status": "INCONCLUSIVE", "reasons": ["No transpiled circuit available."]},
              "functional_equivalence": {"status": "INCONCLUSIVE", "method": "none", "reasons": ["No transpiled circuit available."]},
              "overall_status": "NOT_VERIFIED", "limitations": necessity["limitations"], "comparison": None}
    if error:
        report["transpilation"]["reason"] = str(error)
        return report
    report["target_compatibility"] = verify_target_compatibility(transpiled, constraints)
    report["functional_equivalence"] = verify_functional_equivalence(original, transpiled, limits)
    report["comparison"] = compare_circuit_metrics(original, transpiled)
    original_ops = [i for i in original.data if i.operation.name != "barrier"]
    output_ops = [i for i in transpiled.data if i.operation.name != "barrier"]
    if (report["functional_equivalence"]["status"] == "PASS"
            and report["functional_equivalence"]["method"] == "unitary_operator_equivalence"
            and len(original_ops) == 2 and not output_ops
            and all(isinstance(i.operation, HGate) for i in original_ops)
            and original_ops[0].qubits == original_ops[1].qubits):
        report["comparison"]["explanation"] = (
            "The original circuit consists of two consecutive Hadamard gates on the same qubit. "
            "They cancel because H² = I. The transpiled circuit has no operations, and operator "
            "equivalence independently confirms the identity operation up to global phase.")
    if report["target_compatibility"]["status"] == "PASS" and report["functional_equivalence"]["status"] == "PASS":
        report["overall_status"] = "VERIFIED"
    return report
