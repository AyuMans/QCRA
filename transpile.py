
from qiskit import transpile
import re
from qiskit.circuit import Gate
from qiskit.circuit.library import get_standard_gate_name_mapping

HARDWARE_BASIS_GATES = ["rz", "sx", "x", "cx"]
BASIS_PRESETS = {
    "hardware": ("RZ / SX / X / CX", tuple(HARDWARE_BASIS_GATES)),
    "u_cx": ("U / CX", ("u", "cx")),
    "rx_ry_cz": ("RX / RY / CZ", ("rx", "ry", "cz")),
}
SUPPORTED_BASIS_GATES = tuple(sorted(
    name for name, gate in get_standard_gate_name_mapping().items()
    if isinstance(gate, Gate) and gate.num_qubits > 0
))


def resolve_basis_gates(basis_choice="default", custom_basis_gates=None):
    """Resolve one shared configuration for transpilation and verification.

    A valid gate list need not be universal: Qiskit reports if the submitted
    circuit cannot be expressed in that list. These are not hardware targets.
    """
    if basis_choice == "default":
        return None
    if basis_choice in BASIS_PRESETS:
        return list(BASIS_PRESETS[basis_choice][1])
    if basis_choice != "custom":
        raise ValueError("Invalid basis selection. Choose Qiskit Default, a preset, or Custom basis.")
    if not isinstance(custom_basis_gates, str) or len(custom_basis_gates) > 1000:
        raise ValueError("Enter a custom basis as gate names separated by commas or spaces (up to 1000 characters).")
    names = list(dict.fromkeys(n for n in re.split(r"[\s,]+", custom_basis_gates.strip().lower()) if n))
    if not names:
        raise ValueError("Custom basis is empty. Enter at least one gate, such as rz, sx, x, cx.")
    if len(names) > 32:
        raise ValueError("Choose at most 32 distinct basis gates.")
    unknown = [name for name in names if name not in SUPPORTED_BASIS_GATES]
    if unknown:
        raise ValueError("Unsupported basis gate names: " + ", ".join(unknown) + ". Use the supported gate list. Measurements, resets and barriers are not basis gates.")
    return names


def transpile_circuit(qc, optimization_level=0, basis_choice="default", custom_basis_gates=None):
    """
    Transpile a Qiskit circuit using the selected optimization level
    and basis gate configuration.

    Parameters:
        qc: Original Qiskit QuantumCircuit.
        optimization_level: Integer from 0 to 3.
        basis_choice: "default", a BASIS_PRESETS key, or "custom".
        custom_basis_gates: Comma/space-separated standard gate names.

    Returns:
        The transpiled QuantumCircuit.
    """

    # Validate the optimization level
    if isinstance(optimization_level, bool):
        raise ValueError(
            "Optimization level must be an integer from 0 to 3."
        )

    try:
        optimization_level = int(optimization_level)
    except (TypeError, ValueError):
        raise ValueError(
            "Optimization level must be an integer from 0 to 3."
        )

    if optimization_level not in [0, 1, 2, 3]:
        raise ValueError(
            "Choose an optimization level between 0 and 3."
        )

    # Validate the circuit
    if qc is None:
        raise ValueError("No quantum circuit was provided.")

    # Perform transpilation
    basis_gates = resolve_basis_gates(basis_choice, custom_basis_gates)
    if basis_gates is None:

        transpiled_qc = transpile(
            qc,
            optimization_level=optimization_level
        )

    else:

        transpiled_qc = transpile(
            qc,
            basis_gates=basis_gates,
            optimization_level=optimization_level
        )

    return transpiled_qc
