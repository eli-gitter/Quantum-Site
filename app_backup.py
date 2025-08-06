from flask import Flask, jsonify, render_template, request
import numpy as np
import cmath

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/quantum/execute', methods=['POST'])
def execute_qiskit_code():
    """Execute Qiskit code and return quantum states"""
    print("=== API CALL RECEIVED ===")
    try:
        data = request.get_json()
        code = data.get('code', '')
        print(f"Code to execute: {code[:50]}...")
        
        if not code:
            return jsonify({
                'success': False,
                'error': 'No code provided'
            }), 400
        
        # Create a safe execution environment
        exec_globals = {
            'np': np,
            'cmath': cmath,
            '__builtins__': {
                '__import__': __import__,
                'print': print,
                'len': len,
                'range': range,
                'str': str,
                'int': int,
                'float': float,
            },
        }
        
        # Try to import qiskit
        try:
            import qiskit
            from qiskit import QuantumCircuit
            from qiskit_aer import AerSimulator
            from qiskit.quantum_info import Statevector
            
            print(f"Qiskit imported successfully! Version: {qiskit.__version__}")
            
            exec_globals.update({
                'qiskit': qiskit,
                'QuantumCircuit': QuantumCircuit,
                'AerSimulator': AerSimulator,
                'Statevector': Statevector,
            })
            
        except ImportError as e:
            return jsonify({
                'success': False,
                'error': f'Qiskit import failed: {str(e)}'
            }), 500
        
        exec_locals = {}
        exec(code, exec_globals, exec_locals)

        # Look for quantum circuits in the executed code
        circuits = []
        for name, obj in exec_locals.items():
            if 'QuantumCircuit' in str(type(obj)):
                circuits.append(obj)

        if not circuits:
            print("=== RETURNING SUCCESS ===")
            return jsonify({
                'success': True,
                'output': 'Code executed successfully, but no quantum circuits found',
                'quantum_states': []
            })

        # Extract quantum states from circuits
        quantum_states = []
        for circuit in circuits:
            try:
                # Get the statevector for this circuit
                from qiskit.quantum_info import Statevector

                # Create a clean circuit without measurements
                clean_circuit = QuantumCircuit(circuit.num_qubits)

                # Copy only the quantum gates (not measurements)
                for instruction in circuit.data:
                    if instruction.operation.name != 'measure':
                        clean_circuit.append(instruction.operation, instruction.qubits)

                # Get the statevector
                statevector = Statevector.from_instruction(clean_circuit)
                
                # For single qubit states
                if len(statevector) == 2:
                    alpha, beta = statevector[0], statevector[1]
                    
                    # Convert to Bloch coordinates
                    x = 2 * np.real(np.conj(alpha) * beta)
                    y = 2 * np.imag(np.conj(alpha) * beta)
                    z = np.abs(alpha)**2 - np.abs(beta)**2
                    
                    quantum_states.append({
                        'x': float(x), 
                        'y': float(z), 
                        'z': float(y)
                    })
                else:
                    # Multi-qubit - placeholder for now
                    quantum_states.append({'x': 0, 'y': 1, 'z': 0})
                    
            except Exception as e:
                print(f"Error getting quantum state: {e}")
                quantum_states.append({'x': 0, 'y': 1, 'z': 0})

        print("=== RETURNING SUCCESS ===")
        return jsonify({
            'success': True,
            'output': f'Executed {len(circuits)} quantum circuit(s)',
            'quantum_states': quantum_states
        })
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
        


    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/quantum/state')
def get_state():
    """Get current quantum state in Bloch coordinates"""
    bloch_coords = quantum_state.to_bloch_coordinates()
    alpha, beta = quantum_state.state_vector
    
    return jsonify({
        'bloch_coordinates': bloch_coords,
        'state_vector': {
            'alpha': {'real': float(np.real(alpha)), 'imag': float(np.imag(alpha))},
            'beta': {'real': float(np.real(beta)), 'imag': float(np.imag(beta))}
        },
        'probabilities': {
            'zero': float(np.abs(alpha)**2),
            'one': float(np.abs(beta)**2)
        }
    })

def apply_gate(gate_name):
    """Apply a quantum gate"""
    success = quantum_state.apply_gate(gate_name.upper())
    
    if success:
        new_state = quantum_state.to_bloch_coordinates()
        return jsonify({
            'success': True,
            'gate': gate_name.upper(),
            'new_state': new_state
        })
    else:
        return jsonify({
            'success': False,
            'error': f'Unknown gate: {gate_name}'
        }), 400

def reset_state():
    """Reset to |1⟩ state"""
    quantum_state.reset()
    return jsonify({
        'success': True,
        'new_state': quantum_state.to_bloch_coordinates()
    })

if __name__ == '__main__':
    app.run(debug=True, port=5500)