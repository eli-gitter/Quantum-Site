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
    """Calculate grid dimensions that prefer wider layouts for better centering."""
    if num_qubits <= 0:
        return 1, 1
    elif num_qubits <= 2:
        return 1, num_qubits  # Single row for 1-3 qubits
    elif num_qubits <=4:
        return 2, 2
    elif num_qubits <= 6:
        return 2, 3  # 2 rows, 3 columns for 5-6 qubits
    elif num_qubits <= 9:
        return 3, 3
    else:
        # For larger numbers, use roughly square
        sqrt_n = math.sqrt(num_qubits)
        rows = math.ceil(sqrt_n)
        cols = math.ceil(num_qubits / rows)
        return rows, cols

def statevector_to_bloch_coords(statevector, qubit_index, num_qubits):
    """Convert statevector to Bloch sphere coordinates for a specific qubit."""
    try:
        from qiskit.quantum_info import partial_trace, DensityMatrix
        
        # Convert to density matrix
        rho = DensityMatrix(statevector)
        
        # Get reduced density matrix for the specific qubit
        # Trace out all other qubits
        other_qubits = [i for i in range(num_qubits) if i != qubit_index]
        
        if other_qubits:
            rho_reduced = partial_trace(rho, other_qubits)
        else:
            rho_reduced = rho
        
        # Extract density matrix elements
        rho_matrix = rho_reduced.data
        
        # Calculate Bloch vector components using Pauli expectation values
        # ⟨σ_x⟩ = Tr(ρ σ_x) = 2 * Re(ρ_01)
        # ⟨σ_y⟩ = Tr(ρ σ_y) = 2 * Im(ρ_01)  
        # ⟨σ_z⟩ = Tr(ρ σ_z) = ρ_00 - ρ_11
        
        x = 2 * np.real(rho_matrix[0, 1])
        y = -2 * np.imag(rho_matrix[0, 1])  # Note the minus sign
        z = np.real(rho_matrix[0, 0] - rho_matrix[1, 1])
        
        return [float(x), float(y), float(z)]
        
    except Exception as e:
        print(f"Error calculating Bloch coordinates: {e}")
        return [0, 0, 1]  # Default to |0⟩ state

def get_animation_sequence(circuit, num_qubits):
    """Break circuit into steps and return sequence of Bloch coordinates."""
    # Start with |0...0⟩ state
    current_state = Statevector.from_label('0' * num_qubits)
    
    # Initial state (all qubits at |0⟩)
    sequence = []
    initial_coords = []
    for qubit_idx in range(num_qubits):
        coords = statevector_to_bloch_coords(current_state, qubit_idx, num_qubits)
        initial_coords.append({
            'qubit_index': qubit_idx,
            'coordinates': coords,
            'label': f'Qubit {qubit_idx}'
        })
    
    sequence.append({
        'step': 0,
        'gate_name': 'Initial State',
        'bloch_data': initial_coords
    })
    
    # Apply each gate and capture intermediate states
    step_circuit = QuantumCircuit(num_qubits)
    
    for step, instruction in enumerate(circuit.data):
        gate = instruction[0]
        qubits = [circuit.find_bit(qubit).index for qubit in instruction[1]]        
        # Add this gate to our step circuit
        step_circuit.append(gate, qubits)
        
        # Get new state after this gate
        current_state = Statevector.from_instruction(step_circuit)
        
        # Calculate new Bloch coordinates
        step_coords = []
        for qubit_idx in range(num_qubits):
            coords = statevector_to_bloch_coords(current_state, qubit_idx, num_qubits)
            step_coords.append({
                'qubit_index': qubit_idx,
                'coordinates': coords,
                'label': f'Qubit {qubit_idx}'
            })
        
        sequence.append({
            'step': step + 1,
            'gate_name': gate.name,
            'target_qubits': qubits,
            'bloch_data': step_coords
        })
    
    return sequence

def execute_quantum_code(code):
    """Execute quantum code and return animation sequence."""
    try:
        # Parse number of qubits needed
        num_qubits = parse_qubit_count(code)
        
        # Cap the number of qubits for visualization
        MAX_QUBITS = 9
        if num_qubits > MAX_QUBITS:
            return None, num_qubits, f"Too many qubits for visualization. Maximum supported: {MAX_QUBITS}, requested: {num_qubits}"
        
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
        
        # Get animation sequence by applying gates step by step
        animation_sequence = get_animation_sequence(qc, num_qubits)
        
        return animation_sequence, num_qubits, None
        
    except Exception as e:
        return None, 1, str(e)

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
            'animation_sequence': None
        })
    
    # Execute the quantum code
    animation_sequence, num_qubits, error = execute_quantum_code(code)
    
    if error:
        return jsonify({
            'success': False,
            'error': error,
            'animation_sequence': None
        })
    
    # Calculate grid dimensions
    rows, cols = calculate_grid_dimensions(num_qubits)
    
    return jsonify({
        'success': True,
        'error': None,
        'animation_sequence': animation_sequence,
        'num_qubits': num_qubits,
        'grid_rows': rows,
        'grid_cols': cols
    })

if __name__ == '__main__':
    app.run(debug=True)