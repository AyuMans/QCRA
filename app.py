from flask import Flask, render_template, request

from analyser import analyse_circuit


app = Flask(__name__)


# ============================================================
# HOME PAGE
# ============================================================

@app.route("/", methods=["GET", "POST"])
def index():

    analysis = None

    gates = []

    error = None

    # Default number of qubits
    num_qubits = 3

    # ========================================================
    # USER SUBMITTED THE FORM
    # ========================================================

    if request.method == "POST":

        try:

            # ------------------------------------------------
            # GET NUMBER OF QUBITS
            # ------------------------------------------------

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

            # ------------------------------------------------
            # GET GATE INFORMATION
            # ------------------------------------------------

            gate_names = request.form.getlist("gate")

            q1_values = request.form.getlist("q1")

            q2_values = request.form.getlist("q2")

            # ------------------------------------------------
            # CONVERT FORM DATA INTO GATE OBJECTS
            # ------------------------------------------------

            for i in range(len(gate_names)):

                gate_name = gate_names[i]

                q1 = int(q1_values[i])

                # Validate first qubit
                if q1 < 0 or q1 >= num_qubits:

                    raise ValueError(
                        f"Invalid qubit number: {q1}"
                    )

                # Create gate dictionary
                gate = {

                    "gate": gate_name,

                    "q1": q1

                }

                # ------------------------------------------------
                # TWO-QUBIT GATES
                # ------------------------------------------------

                if gate_name in [
                    "cx",
                    "cz",
                    "swap"
                ]:

                    q2 = int(q2_values[i])

                    if q2 < 0 or q2 >= num_qubits:

                        raise ValueError(
                            f"Invalid target qubit: {q2}"
                        )

                    if q1 == q2:

                        raise ValueError(
                            "Control and target "
                            "qubits cannot be the same."
                        )

                    gate["q2"] = q2

                gates.append(gate)

            # ------------------------------------------------
            # ANALYSE THE CIRCUIT
            # ------------------------------------------------

            analysis = analyse_circuit(
                num_qubits,
                gates
            )

        except ValueError as e:

            error = str(e)

    # ========================================================
    # SEND DATA TO HTML
    # ========================================================

    return render_template(

        "index.html",

        analysis=analysis,

        gates=gates,

        num_qubits=num_qubits,

        error=error
    )


# ============================================================
# START FLASK SERVER
# ============================================================

if __name__ == "__main__":

    app.run(debug=True)