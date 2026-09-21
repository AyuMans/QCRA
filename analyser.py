from qiskit import QuantumCircuit


def analyse_circuit(qc):

    # ========================================================
    # BASIC CIRCUIT INFORMATION
    # ========================================================

    number_of_qubits = qc.num_qubits

    total_operations = qc.size()

    circuit_depth = qc.depth()

    gate_counts = dict(qc.count_ops())

    # ========================================================
    # COUNT SINGLE AND MULTI-QUBIT GATES
    # ========================================================

    single_qubit_gates = 0
    multi_qubit_gates = 0

    for instruction in qc.data:

        number_of_gate_qubits = len(instruction.qubits)

        if number_of_gate_qubits == 1:
            single_qubit_gates += 1

        elif number_of_gate_qubits >= 2:
            multi_qubit_gates += 1

    # ========================================================
    # COUNT ENTANGLING GATES
    # ========================================================

    # CX and CZ are counted as entangling gates.
    # SWAP is a two-qubit gate but does not itself create
    # entanglement.

    entangling_gates = 0

    for gate_name in ["cx", "cz"]:

        if gate_name in gate_counts:
            entangling_gates += gate_counts[gate_name]

    # ========================================================
    # COMPLEXITY
    # ========================================================

    if circuit_depth <= 3:
        complexity = "Low"

    elif circuit_depth <= 10:
        complexity = "Medium"

    else:
        complexity = "High"

    # ========================================================
    # RECOMMENDATIONS
    # ========================================================

    recommendations = []

    if total_operations == 0:

        recommendations.append(
            "No gates have been added to the circuit."
        )

    if circuit_depth > 10:

        recommendations.append(
            "Circuit depth is high. "
            "Consider optimizing the circuit."
        )

    else:

        recommendations.append(
            "Circuit depth is relatively small."
        )

    if multi_qubit_gates > single_qubit_gates:

        recommendations.append(
            "The circuit contains many multi-qubit gates."
        )

    if entangling_gates > 0:

        recommendations.append(
            "Entangling operations are present."
        )

    # ========================================================
    # CIRCUIT DIAGRAM
    # ========================================================

    diagram = str(qc.draw(output="text"))

    # ========================================================
    # RETURN RESULTS
    # ========================================================

    return {

        "qubits": number_of_qubits,

        "operations": total_operations,

        "depth": circuit_depth,

        "gate_counts": gate_counts,

        "single_qubit_gates": single_qubit_gates,

        "multi_qubit_gates": multi_qubit_gates,

        "entangling_gates": entangling_gates,

        "complexity": complexity,

        "recommendations": recommendations,

        "diagram": diagram
    }