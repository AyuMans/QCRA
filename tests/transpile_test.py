from qiskit import QuantumCircuit, transpile


def analyse_circuit(qc):

    # BASIC CIRCUIT INFORMATION

    number_of_qubits = qc.num_qubits
    total_operations = qc.size()
    circuit_depth = qc.depth()
    gate_counts = dict(qc.count_ops())

    # COUNT SINGLE AND MULTI-QUBIT GATES

    single_qubit_gates = 0
    multi_qubit_gates = 0

    for instruction in qc.data:

        number_of_gate_qubits = len(instruction.qubits)

        if number_of_gate_qubits == 1:
            single_qubit_gates += 1

        elif number_of_gate_qubits >= 2:
            multi_qubit_gates += 1

    # COUNT ENTANGLING GATES

    entangling_gates = 0

    for gate_name in ["cx", "cz", "swap", "ecr"]:

        if gate_name in gate_counts:
            entangling_gates += gate_counts[gate_name]

    # COMPLEXITY

    if circuit_depth <= 3:
        complexity = "Low"

    elif circuit_depth <= 10:
        complexity = "Medium"

    else:
        complexity = "High"

    # RECOMMENDATIONS

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

    # CIRCUIT DIAGRAM

    diagram = str(qc.draw(output="text"))

    # RETURN RESULTS

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


# DISPLAY CIRCUIT ANALYSIS

def display_analysis(result, title):

    print("\n" + "=" * 50)
    print(title)
    print("=" * 50)

    print("\nNumber of qubits:", result["qubits"])
    print("Total operations:", result["operations"])
    print("Circuit depth:", result["depth"])

    print("\nGate counts:")

    for gate, count in result["gate_counts"].items():
        print(" ", gate, ":", count)

    print("\nSingle-qubit gates:",
          result["single_qubit_gates"])

    print("Multi-qubit gates:",
          result["multi_qubit_gates"])

    print("Entangling gates:",
          result["entangling_gates"])

    print("Complexity:",
          result["complexity"])

    print("\nRecommendations:")

    for recommendation in result["recommendations"]:
        print("-", recommendation)

    print("\nCircuit diagram:")
    print(result["diagram"])


# READ USER'S QISKIT PROGRAM

print("Paste your Qiskit circuit code.")
print("Enter END on a new line when finished.\n")

code_lines = []

while True:

    line = input()

    if line.strip() == "END":
        break

    code_lines.append(line)

code = "\n".join(code_lines)


# EXECUTE USER CODE

namespace = {}

try:

    exec(code, namespace)

except Exception as e:

    print("\nError while executing the circuit code:")
    print(e)
    raise SystemExit


# FIND QUANTUM CIRCUIT

qc = None

for name, value in namespace.items():

    if isinstance(value, QuantumCircuit):
        qc = value
        break


if qc is None:

    print("\nNo QuantumCircuit was found.")
    raise SystemExit


# ANALYSE ORIGINAL CIRCUIT

original_result = analyse_circuit(qc)

display_analysis(
    original_result,
    "ORIGINAL CIRCUIT ANALYSIS"
)


# ============================================================
# TRANSPILATION SETTINGS
# ============================================================

print("\nTRANSPILATION SETTINGS")
print("Optimization levels: 0, 1, 2, 3")
print("0 = No optimization")
print("1 = Light optimization")
print("2 = Medium optimization")
print("3 = Heavy optimization")

try:

    optimization_level = int(
        input("\nEnter optimization level (0-3): ")
    )

    if optimization_level not in [0, 1, 2, 3]:
        raise ValueError("Choose a level between 0 and 3.")

    print("\nChoose basis gates:")
    print("1. Default Qiskit gates")
    print("2. Hardware-style gates: rz, sx, x, cx")

    choice = input("Enter choice (1 or 2): ").strip()

    if choice == "1":

        # Let Qiskit select its default gate representation.
        transpiled_qc = transpile(
            qc,
            optimization_level=optimization_level
        )

    elif choice == "2":

        basis_gates = ["rz", "sx", "x", "cx"]

        transpiled_qc = transpile(
            qc,
            basis_gates=basis_gates,
            optimization_level=optimization_level
        )

    else:

        raise ValueError("Choose either 1 or 2.")

except Exception as e:

    print("\nTranspilation error:")
    print(e)
    raise SystemExit


# ============================================================
# ANALYSE TRANSPILED CIRCUIT
# ============================================================

transpiled_result = analyse_circuit(transpiled_qc)

display_analysis(
    transpiled_result,
    "TRANSPILED CIRCUIT ANALYSIS"
)


# ============================================================
# COMPARE ORIGINAL AND TRANSPILED CIRCUITS
# ============================================================

print("\n" + "=" * 50)
print("TRANSPILATION COMPARISON")
print("=" * 50)

print("\nMetric                 Original    Transpiled")
print("-" * 50)

print(
    f"Operations             "
    f"{original_result['operations']:<12}"
    f"{transpiled_result['operations']}"
)

print(
    f"Circuit depth          "
    f"{original_result['depth']:<12}"
    f"{transpiled_result['depth']}"
)

print(
    f"Single-qubit gates     "
    f"{original_result['single_qubit_gates']:<12}"
    f"{transpiled_result['single_qubit_gates']}"
)

print(
    f"Multi-qubit gates      "
    f"{original_result['multi_qubit_gates']:<12}"
    f"{transpiled_result['multi_qubit_gates']}"
)


# CALCULATE CHANGES

operation_change = (
    original_result["operations"]
    - transpiled_result["operations"]
)

depth_change = (
    original_result["depth"]
    - transpiled_result["depth"]
)

print("\nOperations reduced:", operation_change)
print("Depth reduced:", depth_change)

if operation_change > 0:
    print("Total operations decreased.")

elif operation_change < 0:
    print("Total operations increased.")

else:
    print("Total operations remained unchanged.")

if depth_change > 0:
    print("Circuit depth decreased.")

elif depth_change < 0:
    print("Circuit depth increased.")

else:
    print("Circuit depth remained unchanged.")


# DISPLAY TRANSPILED CIRCUIT

print("\n" + "=" * 50)
print("FINAL TRANSPILED CIRCUIT")
print("=" * 50)

print(transpiled_qc.draw(output="text"))

print("\nTranspilation completed successfully.")