from flask import Flask, render_template, request, jsonify
import numpy as np
import re
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector
import math

app = Flask(__name__)

def parse_qubit_count(code):
    """Parse the quantum code to determine the number of qubits needed."""
    try:
        # Method 1: Look for QuantumCircuit(n) initialization
        circuit_match = re.search(r'QuantumCircuit\s*\(\s*(\d+)', code)
        if circuit_match:
            return int(circuit_match.group(1))
        
        # Method 2: Find the highest qubit index used
        qubit_indices = re.findall(r'\[\s*(\d+)\s*\]', code)
        if qubit_indices:
            return max(int(idx) for idx in qubit_indices) + 1
        
        # Default to 1 qubit if nothing found
        return 1
    except:
        return 1

def calculate_grid_dimensions(num_qubits):
    """Calculate roughly square grid dimensions for the given number of qubits."""
    if num_qubits <= 0:
        return 1, 1
    
    # Find the square root and round up for rows
    sqrt_n = math.sqrt(num_qubits)
    rows = math.ceil(sqrt_n)
    
    # Calculate columns needed
    cols = math.ceil(num_qubits / rows)
    
    return rows, cols

def execute_quantum_code(code):
    """Execute quantum code and return the statevector and qubit count."""
    try:
        # Parse number of qubits needed
        num_qubits = parse_qubit_count(code)
        
        # Create a namespace for execution
        namespace = {
            'QuantumCircuit': QuantumCircuit,
            'np': np,
            'math': math,
            'pi': np.pi
        }
        
        # Execute the code
        exec(code, namespace)
        
        # Try to find the quantum circuit in the namespace
        qc = None
        for var_name, var_value in namespace.items():
            if isinstance(var_value, QuantumCircuit):
                qc = var_value
                break
        
        if qc is None:
            return None, num_qubits, "No quantum circuit found in code"
        
        # Update num_qubits based on actual circuit if found
        num_qubits = qc.num_qubits
        
        # Get the statevector
        statevector = Statevector.from_instruction(qc)
        
        return statevector, num_qubits, None
        
    except Exception as e:
        return None, 1, str(e)

def statevector_to_bloch_coords(statevector, qubit_index, num_qubits):
    """Convert statevector to Bloch sphere coordinates for a specific qubit."""
    try:
        # Get the reduced density matrix for the specific qubit
        # This is a simplified approach - for a more accurate representation,
        # we should compute the partial trace
        
        # For now, let's use a simplified approach
        # Get the amplitudes for states where this qubit is |0⟩ and |1⟩
        amplitudes = statevector.data
        
        # Calculate Bloch vector components using expectation values
        # This is a simplified calculation
        prob_0 = 0
        prob_1 = 0
        phase_sum = 0
        
        for i, amp in enumerate(amplitudes):
            # Check if qubit_index-th bit is 0 or 1 in state i
            if (i >> qubit_index) & 1 == 0:  # qubit is in |0⟩
                prob_0 += abs(amp) ** 2
            else:  # qubit is in |1⟩
                prob_1 += abs(amp) ** 2
                phase_sum += np.angle(amp)
        
        # Calculate Bloch coordinates (simplified)
        z = prob_0 - prob_1
        
        # For x and y, we need coherence terms (simplified approach)
        x = 2 * np.sqrt(prob_0 * prob_1) * np.cos(phase_sum)
        y = 2 * np.sqrt(prob_0 * prob_1) * np.sin(phase_sum)
        
        return [float(x), float(y), float(z)]
        
    except Exception as e:
        print(f"Error calculating Bloch coordinates: {e}")
        return [0, 0, 1]  # Default to |0⟩ state

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/execute', methods=['POST'])
def execute():
    code = request.json.get('code', '')
    
    if not code.strip():
        return jsonify({
            'success': False,
            'error': 'No code provided',
            'bloch_data': None
        })
    
    # Execute the quantum code
    statevector, num_qubits, error = execute_quantum_code(code)
    
    if error:
        return jsonify({
            'success': False,
            'error': error,
            'bloch_data': None
        })
    
    # Calculate Bloch coordinates for each qubit
    bloch_data = []
    for qubit_idx in range(num_qubits):
        coords = statevector_to_bloch_coords(statevector, qubit_idx, num_qubits)
        bloch_data.append({
            'qubit_index': qubit_idx,
            'coordinates': coords,
            'label': f'Qubit {qubit_idx}'
        })
    
    # Calculate grid dimensions
    rows, cols = calculate_grid_dimensions(num_qubits)
    
    return jsonify({
        'success': True,
        'error': None,
        'bloch_data': bloch_data,
        'num_qubits': num_qubits,
        'grid_rows': rows,
        'grid_cols': cols
    })

if __name__ == '__main__':
    app.run(debug=True)