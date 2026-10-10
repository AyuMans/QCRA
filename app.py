from flask import Flask, render_template, request

from qiskit import QuantumCircuit

from analyser import analyse_circuit


app = Flask(__name__)


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
    # FORM SUBMITTED
    # ========================================================

    if request.method == "POST":

        form_type = request.form.get(
            "form_type",
            "builder"
        )


        # ====================================================
        # CIRCUIT BUILDER
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

                analysis = analyse_circuit(qc)


            except ValueError as e:

                error = str(e)


        # ====================================================
        # CODE ANALYSER
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


    # ========================================================
    # RENDER PAGE
    # ========================================================

    return render_template(

        "index.html",

        analysis=analysis,

        error=error,

        active_tab=active_tab,

        gates=gates,

        num_qubits=num_qubits,

        code=code

    )


# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == "__main__":

    app.run(debug=True)