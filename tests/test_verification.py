"""Run with: python -m unittest discover -s tests -p 'test_*.py'."""
import unittest
from unittest.mock import patch

from qiskit import QuantumCircuit, transpile
from qiskit.circuit import Instruction, Parameter
from qiskit.circuit.library import CXGate, XGate
from qiskit.transpiler import Target, CouplingMap
from werkzeug.datastructures import MultiDict

from app import app
from analyser import analyse_circuit
from transpile import transpile_circuit, resolve_basis_gates, BASIS_PRESETS
from verification import (VerificationLimits, check_transpilation_necessity,
                          verify_target_compatibility, verify_functional_equivalence,
                          selected_constraints, generate_verification_report)


class VerificationTests(unittest.TestCase):
    def setUp(self):
        self.constraints = selected_constraints('hardware')

    def test_basis_presets(self):
        qc = QuantumCircuit(2)
        qc.h(0)
        qc.cx(0, 1)
        for choice in BASIS_PRESETS:
            with self.subTest(choice=choice):
                output = transpile_circuit(qc, 2, choice)
                self.assertTrue(set(output.count_ops()) <= set(resolve_basis_gates(choice)))
                self.assertEqual(verify_target_compatibility(output, selected_constraints(choice))['status'], 'PASS')
                self.assertEqual(verify_functional_equivalence(qc, output)['status'], 'PASS')

    def test_custom_basis_validation(self):
        self.assertEqual(resolve_basis_gates('custom', ' RZ, sx X, CX, rz '), ['rz', 'sx', 'x', 'cx'])
        self.assertEqual(resolve_basis_gates('default', 'ignored'), None)
        for value in ('', ' , ', 'unknown', 'measure', 'reset', 'barrier', '<script>', 'x' * 1001):
            with self.subTest(value=value[:30]), self.assertRaises(ValueError):
                resolve_basis_gates('custom', value)
        with self.assertRaises(ValueError):
            resolve_basis_gates('not-a-preset')

    def test_custom_basis_drives_all_checks(self):
        qc = QuantumCircuit(1)
        qc.h(0)
        compatible = selected_constraints('custom', 'h')
        self.assertEqual(check_transpilation_necessity(qc, compatible)['status'], 'NOT_REQUIRED')
        constraints = selected_constraints('custom', 'u, cx')
        necessity = check_transpilation_necessity(qc, constraints)
        self.assertEqual(necessity['status'], 'REQUIRED')
        output = transpile_circuit(qc, 2, 'custom', 'u, cx')
        report = generate_verification_report(qc, output, constraints, necessity)
        self.assertEqual(report['overall_status'], 'VERIFIED')
        self.assertTrue(set(output.count_ops()) <= {'u', 'cx'})

    def test_custom_basis_web_and_errors(self):
        client = app.test_client()
        form = {'form_type': 'code', 'action': 'transpile', 'basis_choice': 'custom',
                'optimization_level': '2', 'custom_basis_gates': 'u, cx',
                'code': 'from qiskit import QuantumCircuit\nqc=QuantumCircuit(1)\nqc.h(0)'}
        success = client.post('/', data=form)
        self.assertEqual(success.status_code, 200)
        self.assertIn(b'Applied basis: <code>u, cx</code>', success.data)
        self.assertIn(b'Gate-set compatibility', success.data)
        self.assertIn(b'value="u, cx"', success.data)
        self.assertIn(b'Overall verification: <strong>VERIFIED', success.data)
        for gates in ('', 'invalid_gate', 'x'):
            # x is recognized, but cannot represent H: a controlled transpiler error.
            with self.subTest(gates=gates):
                response = client.post('/', data={**form, 'custom_basis_gates': gates})
                self.assertEqual(response.status_code, 200)
                self.assertIn(b'Error during transpilation:', response.data)
                self.assertIn(('value="' + gates + '"').encode(), response.data)
                self.assertNotIn(b'Overall verification: <strong>VERIFIED', response.data)
                self.assertNotIn(b'Traceback', response.data)
        # Choosing a custom set must not prevent ordinary analysis.
        response = client.post('/', data={**form, 'action': 'analyse', 'custom_basis_gates': ''})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b'class="error"', response.data)

    def test_compatible_and_optional(self):
        qc = QuantumCircuit(2)
        qc.x(0)
        qc.cx(0, 1)
        self.assertEqual(check_transpilation_necessity(qc, self.constraints)['status'], 'NOT_REQUIRED')
        self.assertEqual(check_transpilation_necessity(qc, self.constraints, True)['status'], 'OPTIONAL')
        self.assertEqual(verify_target_compatibility(qc, self.constraints)['status'], 'PASS')

    def test_missing_target(self):
        self.assertEqual(check_transpilation_necessity(QuantumCircuit(1))['status'], 'UNDETERMINED')

    def test_decomposition_and_nonmutation(self):
        qc = QuantumCircuit(1)
        qc.h(0)
        saved = qc.copy()
        necessity = check_transpilation_necessity(qc, self.constraints)
        self.assertEqual(necessity['status'], 'REQUIRED')
        out = transpile_circuit(qc, 2, 'hardware')
        report = generate_verification_report(qc, out, self.constraints, necessity)
        self.assertEqual(report['overall_status'], 'VERIFIED')
        self.assertEqual(qc, saved)

    def test_redundant_gates(self):
        qc = QuantumCircuit(1)
        qc.h(0)
        qc.h(0)
        out = transpile_circuit(qc, 2)
        self.assertEqual(out.size(), 0)
        self.assertEqual(verify_functional_equivalence(qc, out)['status'], 'PASS')
        report = generate_verification_report(qc, out, self.constraints, check_transpilation_necessity(qc, self.constraints))
        self.assertIn('H² = I', report['comparison']['explanation'])
        self.assertEqual(report['functional_equivalence']['matrices']['original'], [['1', '0'], ['0', '1']])

    def test_different_representation(self):
        a, b = QuantumCircuit(1), QuantumCircuit(1)
        a.x(0)
        b.h(0)
        b.z(0)
        b.h(0)
        self.assertEqual(verify_functional_equivalence(a, b)['status'], 'PASS')

    def test_incorrect_and_phase(self):
        a, b = QuantumCircuit(1), QuantumCircuit(1)
        b.x(0)
        self.assertEqual(verify_functional_equivalence(a, b)['status'], 'FAIL')
        b = a.copy()
        b.global_phase = 0.73
        self.assertEqual(verify_functional_equivalence(a, b)['status'], 'PASS')
        result = verify_functional_equivalence(a, b)
        self.assertAlmostEqual(result['global_phase_radians'], -0.73)
        self.assertLess(result['phase_aligned_max_difference'], 1e-8)
        self.assertNotEqual(result['matrices']['original'], result['matrices']['transpiled'])

    def test_matrix_display_limit_and_serialization(self):
        import json
        qc = QuantumCircuit(4)
        result = verify_functional_equivalence(qc, qc)
        self.assertEqual(result['status'], 'PASS')
        self.assertIsNone(result['matrices'])
        self.assertEqual(result['matrix_dimension'], 16)
        json.dumps(result, allow_nan=False)
        small = QuantumCircuit(1)
        small.s(0)
        result = verify_functional_equivalence(small, small)
        self.assertEqual(result['matrices']['original'][1][1], '1i')
        json.dumps(result, allow_nan=False)
        # Display rounding must never determine verification.
        other = QuantumCircuit(1)
        other.rz(1e-5, 0)
        result = verify_functional_equivalence(QuantumCircuit(1), other)
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual(result['matrices']['original'], result['matrices']['transpiled'])

    def test_limits_skip_operator_construction(self):
        qc = QuantumCircuit(9)
        with patch('verification.Operator.from_circuit') as operator:
            result = verify_functional_equivalence(qc, qc)
        operator.assert_not_called()
        self.assertEqual(result['status'], 'INCONCLUSIVE')
        self.assertIsNone(result['matrices'])

    def test_terminal_measurement(self):
        qc = QuantumCircuit(2, 3)
        qc.h(0)
        qc.cx(0, 1)
        qc.measure(0, 2)
        qc.measure(1, 0)
        out = transpile_circuit(qc, 2, 'hardware')
        result = verify_functional_equivalence(qc, out)
        self.assertEqual(result['status'], 'PASS')
        self.assertIsNone(result['matrices'])
        self.assertIn('no complete unitary matrix', result['matrix_message'])
        rows = result['output_comparison']['rows']
        self.assertAlmostEqual(rows[0]['original'], .5)
        self.assertAlmostEqual(rows[5]['original'], .5)
        self.assertEqual(verify_target_compatibility(out, self.constraints)['status'], 'INCONCLUSIVE')

    def test_measurement_mapping_mismatch(self):
        a = QuantumCircuit(2, 1)
        a.x(0)
        b = a.copy()
        a.measure(0, 0)
        b.measure(1, 0)
        self.assertEqual(verify_functional_equivalence(a, b)['status'], 'FAIL')

    def test_matching_zero_input_not_universal(self):
        a, b = QuantumCircuit(1, 1), QuantumCircuit(1, 1)
        b.z(0)
        a.measure(0, 0)
        b.measure(0, 0)
        result = verify_functional_equivalence(a, b)
        self.assertEqual(result['status'], 'INCONCLUSIVE')
        self.assertFalse(result['universal'])

    def test_unsupported(self):
        for kind in ('reset', 'intermediate', 'custom', 'dynamic'):
            with self.subTest(kind=kind):
                qc = QuantumCircuit(1, 1)
                if kind == 'reset':
                    qc.reset(0)
                elif kind == 'intermediate':
                    qc.measure(0, 0)
                    qc.x(0)
                elif kind == 'dynamic':
                    with qc.if_test((qc.clbits[0], True)):
                        qc.x(0)
                else:
                    qc.append(Instruction('opaque', 1, 0, []), [0])
                self.assertEqual(verify_functional_equivalence(qc, qc)['status'], 'UNSUPPORTED')

    def test_limits_and_parameters(self):
        qc = QuantumCircuit(3)
        self.assertEqual(verify_functional_equivalence(qc, qc, VerificationLimits(max_qubits=2))['status'], 'INCONCLUSIVE')
        qc.rx(Parameter('theta'), 0)
        self.assertEqual(verify_functional_equivalence(qc, qc)['status'], 'INCONCLUSIVE')
        self.assertEqual(verify_functional_equivalence(QuantumCircuit(1), QuantumCircuit(2))['status'], 'INCONCLUSIVE')

    def test_directed_target_and_capacity(self):
        # Synthetic fixture only; the application does not advertise this as hardware.
        target = Target(num_qubits=2)
        target.add_instruction(CXGate(), {(0, 1): None})
        target.add_instruction(XGate(), {(0,): None})
        qc = QuantumCircuit(2)
        qc.cx(1, 0)
        self.assertEqual(check_transpilation_necessity(qc, {'target': target})['status'], 'REQUIRED')
        self.assertEqual(verify_target_compatibility(qc, {'target': target})['status'], 'FAIL')
        self.assertEqual(check_transpilation_necessity(QuantumCircuit(3), {'target': target})['status'], 'UNSUPPORTED')
        self.assertEqual(verify_target_compatibility(QuantumCircuit(3), {'target': target})['status'], 'FAIL')
        qc = QuantumCircuit(2)
        qc.x(1)
        self.assertEqual(check_transpilation_necessity(qc, {'target': target})['status'], 'REQUIRED')

    def test_layout_and_routing(self):
        qc = QuantumCircuit(3)
        qc.h(0)
        qc.cx(0, 2)
        qc.x(1)
        out = transpile(qc, basis_gates=['rz', 'sx', 'x', 'cx'],
                        coupling_map=CouplingMap([[0, 1], [1, 0], [1, 2], [2, 1]]),
                        initial_layout=[2, 0, 1], optimization_level=0, seed_transpiler=42)
        self.assertEqual(verify_functional_equivalence(qc, out)['status'], 'PASS')

    def test_regression_and_web(self):
        qc = QuantumCircuit(2)
        qc.h(0)
        qc.cx(0, 1)
        analysis = analyse_circuit(qc)
        self.assertEqual((analysis['operations'], analysis['depth'], analysis['entangling_gates']), (2, 2, 1))
        self.assertTrue(analysis['diagram'])
        self.assertTrue(analysis['recommendations'])
        client = app.test_client()
        self.assertEqual(client.get('/').status_code, 200)
        form = MultiDict([('form_type', 'builder'), ('num_qubits', '2'), ('gate', 'h'), ('q1', '0'), ('gate', 'cx'), ('q1', '0'), ('q2', '1')])
        normal = client.post('/', data=form)
        self.assertEqual(normal.status_code, 200)
        self.assertNotIn(b'id="transpilation-verification"', normal.data)
        form.update({'action': 'transpile', 'basis_choice': 'hardware', 'optimization_level': '2'})
        response = client.post('/', data=form)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Overall verification: <strong>VERIFIED', response.data)
        self.assertIn(b'Original circuit', response.data)
        with patch('app.transpile_circuit', side_effect=RuntimeError('test failure')):
            failure = client.post('/', data=form)
        self.assertEqual(failure.status_code, 200)
        self.assertIn(b'NOT_VERIFIED', failure.data)
        self.assertIn(b'test failure', failure.data)
        code = 'from qiskit import QuantumCircuit\nqc = QuantumCircuit(1, 1)\nqc.h(0)\nqc.measure(0, 0)'
        response = client.post('/', data={'form_type': 'code', 'code': code, 'action': 'transpile', 'basis_choice': 'hardware', 'optimization_level': '2'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'unitary prefix and identical terminal measurements', response.data)

    def test_result_panels_and_matrix_rendering(self):
        from html.parser import HTMLParser
        class Page(HTMLParser):
            def __init__(self):
                super().__init__()
                self.stack, self.elements = [], {}
            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if 'id' in attrs:
                    self.assert_unique(attrs['id'])
                    self.elements[attrs['id']] = (attrs, list(self.stack))
                if tag not in ('input', 'link', 'meta', 'br', 'hr', 'img'):
                    self.stack.append(attrs.get('id', tag))
            def assert_unique(self, key):
                if key in self.elements:
                    raise AssertionError('Duplicate id: ' + key)
            def handle_endtag(self, tag):
                if self.stack:
                    self.stack.pop()
        form = {'form_type': 'code', 'action': 'transpile', 'basis_choice': 'hardware', 'optimization_level': '2',
                'code': 'from qiskit import QuantumCircuit\nqc=QuantumCircuit(1)\nqc.h(0)\nqc.h(0)'}
        response = app.test_client().post('/', data=form)
        self.assertEqual(response.status_code, 200)
        text = response.get_data(as_text=True)
        page = Page()
        page.feed(text)
        for name in ('original', 'analysis', 'verification', 'comparison'):
            attrs, parents = page.elements['report-' + name + '-panel']
            self.assertEqual('hidden' in attrs, name != 'analysis')
            self.assertEqual(attrs['aria-labelledby'], 'report-' + name + '-tab')
            self.assertNotIn('report-analysis-panel', parents)
        self.assertIn('report-verification-panel', page.elements['transpilation-verification'][1])
        self.assertIn('report-comparison-panel', page.elements['verification-comparison'][1])
        self.assertIn('View matrices', text)
        self.assertIn('H² = I', text)
        self.assertIn('matrix-scroll', text)
        self.assertIn('Results overview', text)
        self.assertIn('Return to results', text)

    def test_errors_and_default_target_rendering(self):
        client = app.test_client()
        for code in ('', 'not python code!', 'x=1'):
            result = client.post('/', data={'form_type': 'code', 'code': code})
            self.assertEqual(result.status_code, 200)
            self.assertIn(b'class="error"', result.data)
            self.assertNotIn(b'Traceback', result.data)
        response = client.post('/', data={'form_type': 'code', 'action': 'transpile',
                                         'code': 'from qiskit import QuantumCircuit\nqc=QuantumCircuit(1)',
                                         'basis_choice': 'default'})
        self.assertIn(b'UNDETERMINED', response.data)
        self.assertIn(b'No execution target', response.data)
        self.assertIn(b'NOT_VERIFIED', response.data)


if __name__ == '__main__':
    unittest.main()
