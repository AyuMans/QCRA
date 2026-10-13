
from qiskit import transpile


def transpile_circuit(qc, optimization_level=0, basis_choice="default"):
    """
    Transpile a Qiskit circuit using the selected optimization level
    and basis gate configuration.

    Parameters:
        qc: Original Qiskit QuantumCircuit.
        optimization_level: Integer from 0 to 3.
        basis_choice: "default" or "hardware".

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
    if basis_choice == "default":

        transpiled_qc = transpile(
            qc,
            optimization_level=optimization_level
        )

    elif basis_choice == "hardware":

        basis_gates = ["rz", "sx", "x", "cx"]

        transpiled_qc = transpile(
            qc,
            basis_gates=basis_gates,
            optimization_level=optimization_level
        )

    else:
        raise ValueError(
            "Invalid basis gate selection. "
            "Choose 'default' or 'hardware'."
        )

    return transpiled_qc
