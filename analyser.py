from qiskit import QuantumCircuit


def analyse_circuit(num_qubits, gates):

    # ========================================================
    # CREATE QISKIT CIRCUIT
    # ========================================================

    qc = QuantumCircuit(num_qubits)

    # ========================================================
    # ADD USER'S GATES TO THE CIRCUIT
    # ========================================================

    for gate in gates:

        gate_type = gate["gate"]
        q1 = gate["q1"]

        # ----------------------------------------------------
        # SINGLE-QUBIT GATES
        # ----------------------------------------------------

        if gate_type == "h":
            qc.h(q1)

        elif gate_type == "x":
            qc.x(q1)

        elif gate_type == "y":
            qc.y(q1)

        elif gate_type == "z":
            qc.z(q1)

        elif gate_type == "s":
            qc.s(q1)

        elif gate_type == "t":
            qc.t(q1)

        # ----------------------------------------------------
        # TWO-QUBIT GATES
        # ----------------------------------------------------

        elif gate_type == "cx":

            q2 = gate["q2"]

            qc.cx(q1, q2)

        elif gate_type == "cz":

            q2 = gate["q2"]

            qc.cz(q1, q2)

        elif gate_type == "swap":

            q2 = gate["q2"]

            qc.swap(q1, q2)

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

        number_of_gate_qubits = len(
            instruction.qubits
        )

        if number_of_gate_qubits == 1:

            single_qubit_gates += 1

        elif number_of_gate_qubits >= 2:

            multi_qubit_gates += 1

    # ========================================================
    # COUNT ENTANGLING GATES
    # ========================================================

    entangling_gates = 0

    for gate_name in ["cx", "cz", "swap"]:

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
    # CREATE TEXT CIRCUIT DIAGRAM
    # ========================================================

    diagram = str(
        qc.draw(output="text")
    )

    # ========================================================
    # RETURN ANALYSIS
    # ========================================================

    return {

        "qubits": number_of_qubits,

        "operations": total_operations,

        "depth": circuit_depth,

        "gate_counts": gate_counts,

        "single_qubit_gates":
            single_qubit_gates,

        "multi_qubit_gates":
            multi_qubit_gates,

        "entangling_gates":
            entangling_gates,

        "complexity":
            complexity,

        "recommendations":
            recommendations,

        "diagram":
            diagram
    }