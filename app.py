
from flask import Flask, render_template, request

from qiskit import QuantumCircuit

from analyser import analyse_circuit

# NEW: Import the transpilation function
from transpile import transpile_circuit, BASIS_PRESETS, SUPPORTED_BASIS_GATES
from verification import (VerificationLimits, selected_constraints,
                          check_transpilation_necessity, generate_verification_report)


app = Flask(__name__)
app.config.setdefault("VERIFICATION_LIMITS", VerificationLimits())


# ============================================================
# FIND QUANTUM CIRCUIT FROM USER CODE
# ============================================================

def get_circuit_from_code(code):

    namespace = {}

    # Execute the user's Qiskit code
    exec(code, namespace)

    # Search for a QuantumCircuit object
    for name, value in namespace.items():

        if isinstance(value, QuantumCircuit):

            return value

    return None


# ============================================================
# CREATE CIRCUIT FROM BUILDER INPUT
# ============================================================

def create_circuit_from_builder(num_qubits, gates):

    qc = QuantumCircuit(num_qubits)

    for gate in gates:

        gate_type = gate["gate"]

        q1 = gate["q1"]

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

        elif gate_type == "cx":

            q2 = gate["q2"]

            qc.cx(q1, q2)

        elif gate_type == "cz":

            q2 = gate["q2"]

            qc.cz(q1, q2)

        elif gate_type == "swap":

            q2 = gate["q2"]

            qc.swap(q1, q2)

    return qc


# ============================================================
# MAIN ROUTE
# ============================================================

@app.route("/", methods=["GET", "POST"])
def index():

    analysis = None

    error = None

    active_tab = "builder"

    # Used by the circuit builder
    gates = []

    num_qubits = 3

    # Used by the code analyser
    code = ""

    # ========================================================
    # NEW: VARIABLES USED ONLY FOR TRANSPILATION RESULTS
    # ========================================================

    original_analysis = None

    transpiled_analysis = None

    transpiled_diagram = None

    transpilation_settings = None

    comparison = None
    transpilation_verification = None

    # NEW: Keep track of the circuit created by the existing
    # Builder or Code Analyser so it can also be transpiled.
    qc = None

    # NEW: Default action preserves the existing analysis flow.
    action = "analyse"


    # ========================================================
    # FORM SUBMITTED
    # ========================================================

    if request.method == "POST":

        form_type = request.form.get(
            "form_type",
            "builder"
        )

        # NEW: Transpilation is an additional action.
        # Existing forms that don't submit this field default
        # to normal analysis.
        action = request.form.get(
            "action",
            "analyse"
        )


        # ====================================================
        # CIRCUIT BUILDER
        # EXISTING FUNCTIONALITY
        # ====================================================

        if form_type == "builder":

            active_tab = "builder"

            try:

                num_qubits = int(
                    request.form.get(
                        "num_qubits",
                        3
                    )
                )

                if num_qubits < 1:

                    raise ValueError(
                        "Number of qubits must be at least 1."
                    )


                gate_names = request.form.getlist("gate")
                q1_values = request.form.getlist("q1")
                q2_values = request.form.getlist("q2")

                if len(gate_names) != len(q1_values):
                    raise ValueError(
                        "Gate information is incomplete. Please rebuild the circuit."
                    )

                target_index = 0

                for i, gate_name in enumerate(gate_names):
                    q1 = int(q1_values[i])

                    if q1 < 0 or q1 >= num_qubits:
                        raise ValueError(f"Invalid qubit number: {q1}")

                    gate = {"gate": gate_name, "q1": q1}

                    if gate_name in ["cx", "cz", "swap"]:
                        if target_index >= len(q2_values):
                            raise ValueError("Please select a target qubit.")

                        q2 = int(q2_values[target_index])
                        target_index += 1

                        if q2 < 0 or q2 >= num_qubits:
                            raise ValueError(f"Invalid target qubit: {q2}")

                        if q1 == q2:
                            raise ValueError(
                                "Control and target qubits cannot be the same."
                            )

                        gate["q2"] = q2

                    gates.append(gate)


                # Create Qiskit circuit

                qc = create_circuit_from_builder(
                    num_qubits,
                    gates
                )


                # Analyse circuit
                # EXISTING BEHAVIOUR: analysis is the original
                # circuit's analysis, as before.

                analysis = analyse_circuit(qc)


            except ValueError as e:

                error = str(e)


        # ====================================================
        # CODE ANALYSER
        # EXISTING FUNCTIONALITY
        # ====================================================

        elif form_type == "code":

            active_tab = "code"

            code = request.form.get(
                "code",
                ""
            )


            if not code.strip():

                error = "Please enter Qiskit code."


            else:

                try:

                    qc = get_circuit_from_code(code)


                    if qc is None:

                        error = (
                            "No QuantumCircuit was found. "
                            "Please create a circuit using "
                            "QuantumCircuit()."
                        )

                    else:

                        analysis = analyse_circuit(qc)


                except Exception as e:

                    error = (
                        "Error while executing the "
                        "Qiskit code: "
                        + str(e)
                    )


        # ====================================================
        # NEW FEATURE: CIRCUIT TRANSPILATION
        # Runs only when the Transpile button is submitted.
        # ====================================================

        if (
            action == "transpile"
            and qc is not None
            and error is None
        ):

            try:

                # Get transpilation settings from the frontend.

                optimization_level = request.form.get(
                    "optimization_level",
                    "0"
                )

                basis_choice = request.form.get(
                    "basis_choice",
                    "default"
                )


                # Preserve the original circuit's analysis
                # separately for the comparison.

                original_analysis = analysis


                # Transpile the original circuit.

                custom_basis_gates = request.form.get("custom_basis_gates", "")
                constraints = selected_constraints(basis_choice, custom_basis_gates)
                necessity = check_transpilation_necessity(
                    qc, constraints, optimization_requested=int(optimization_level) > 0
                )

                try:
                    transpiled_qc = transpile_circuit(
                        qc,
                        optimization_level=optimization_level,
                        basis_choice=basis_choice,
                        custom_basis_gates=custom_basis_gates
                    )
                except Exception as exc:
                    transpilation_verification = generate_verification_report(
                        qc, None, constraints, necessity, error=exc
                    )
                    raise

                transpilation_verification = generate_verification_report(
                    qc, transpiled_qc, constraints, necessity,
                    limits=app.config["VERIFICATION_LIMITS"]
                )


                # Analyse the transpiled circuit separately.

                transpiled_analysis = analyse_circuit(
                    transpiled_qc
                )


                # Generate a text representation of the
                # transpiled circuit for the frontend.

                transpiled_diagram = str(
                    transpiled_qc.draw(output="text")
                )


                # Compare original and transpiled resources.

                original_operations = original_analysis["operations"]

                transpiled_operations = (
                    transpiled_analysis["operations"]
                )

                original_depth = original_analysis["depth"]

                transpiled_depth = transpiled_analysis["depth"]


                operation_change = (
                    original_operations - transpiled_operations
                )

                depth_change = (
                    original_depth - transpiled_depth
                )


                # Pass comparison values to the frontend.

                comparison = {

                    "original_operations":
                        original_operations,

                    "transpiled_operations":
                        transpiled_operations,

                    "original_depth":
                        original_depth,

                    "transpiled_depth":
                        transpiled_depth,

                    "original_single_qubit_gates":
                        original_analysis["single_qubit_gates"],

                    "transpiled_single_qubit_gates":
                        transpiled_analysis["single_qubit_gates"],

                    "original_multi_qubit_gates":
                        original_analysis["multi_qubit_gates"],

                    "transpiled_multi_qubit_gates":
                        transpiled_analysis["multi_qubit_gates"],

                    "operation_change":
                        operation_change,

                    "depth_change":
                        depth_change
                }


                # Preserve the selected settings for the UI.

                transpilation_settings = {

                    "optimization_level":
                        int(optimization_level),

                    "basis_choice":
                        basis_choice,
                    "basis_gates": constraints["basis_gates"]
                }


            except Exception as e:

                error = (
                    "Error during transpilation: "
                    + str(e)
                )


    # ========================================================
    # RENDER PAGE
    # EXISTING VARIABLES ARE PRESERVED.
    # NEW VARIABLES ARE ADDED FOR TRANSPILATION.
    # ========================================================

    return render_template(

        "index.html",

        # Existing template variables
        analysis=analysis,

        error=error,

        active_tab=active_tab,

        gates=gates,

        num_qubits=num_qubits,

        code=code,

        # NEW: Transpilation template variables
        original_analysis=original_analysis,

        transpiled_analysis=transpiled_analysis,

        transpiled_diagram=transpiled_diagram,

        transpilation_settings=transpilation_settings,

        comparison=comparison,
        transpilation_verification=transpilation_verification,
        basis_presets=BASIS_PRESETS,
        supported_basis_gates=SUPPORTED_BASIS_GATES,
        selected_basis_choice=request.form.get("basis_choice", "default"),
        custom_basis_input=request.form.get("custom_basis_gates", ""),
        selected_optimization_level=request.form.get("optimization_level", "0")

    )


# ============================================================
# RUN APPLICATION
# EXISTING FUNCTIONALITY
# ============================================================

if __name__ == "__main__":

    app.run(debug=True)

