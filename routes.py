from flask import Blueprint, request, jsonify
from models import db, DeviceData, NeighborCell, PendingCommand
from flask_socketio import emit
from datetime import datetime

device_routes = Blueprint('device_routes', __name__)

# Rota para receber dados do dispositivo e armazená-los
@device_routes.route('/receive_data', methods=['POST'])
def receive_data():
    data = request.json
    device_id = data['device_id']

    # Validação e criação/atualização de DeviceData e NeighborCell
    device_data = DeviceData.query.filter_by(device_id=device_id).first()
    
    if device_data:
        db.session.delete(device_data.neighbor_cells)  # Exclui as células vizinhas existentes para atualização
    else:
        device_data = DeviceData(device_id=device_id)
        db.session.add(device_data)

    # Atualiza ou adiciona os campos de DeviceData
    for key, value in data.items():
        if hasattr(device_data, key):
            setattr(device_data, key, value)

    # Adiciona as novas Neighbor Cells
    for neighbor in data.get('neighbor_cells', []):
        neighbor_cell = NeighborCell(device_data=device_data, **neighbor)
        db.session.add(neighbor_cell)

    db.session.commit()
    
    # Emite o evento para os clientes conectados
    emit('new_data', data, broadcast=True)
    return jsonify({'status': 'success'})

# Rota para obter os dados mais recentes de cada dispositivo
@device_routes.route('/latest_data', methods=['GET'])
def get_latest_data():
    devices = DeviceData.query.order_by(DeviceData.device_id, DeviceData.created_at.desc()).distinct(DeviceData.device_id)
    data = [device.to_dict() for device in devices]
    return jsonify(data), 200

# Rota para enviar comandos ao dispositivo e salvar no banco
@device_routes.route('/send_command', methods=['POST'])
def send_command():
    data = request.json
    device_id = data.get("device_id")
    command_type = data.get("command_type")

    if not device_id or not command_type:
        return jsonify({"status": "error", "message": "Campos device_id e command_type são obrigatórios"}), 400

    command_map = {
        "ReqICCID": f"ST410CMD;{device_id};02;ReqICCID\n",
        "StartEmg": f"ST410CMD;{device_id};02;StartEmg\n",
        "StopEmg": f"ST410CMD;{device_id};02;StopEmg\n"
    }

    command = command_map.get(command_type)
    if not command:
        return jsonify({"status": "error", "message": "Comando inválido"}), 400

    # Salva o comando como pendente no banco de dados
    pending_command = PendingCommand(device_id=device_id, command=command)
    db.session.add(pending_command)
    db.session.commit()

    return jsonify({"status": "success", "message": "Comando salvo e aguardando envio"}), 200

# Rota para verificar comandos pendentes para um dispositivo específico
@device_routes.route('/check_pending_commands', methods=['GET'])
def check_pending_commands():
    """
    Verifica comandos pendentes para o dispositivo especificado.
    """
    device_id = request.args.get('device_id')
    if not device_id:
        return jsonify({"status": "error", "message": "device_id é obrigatório"}), 400

    pending_commands = PendingCommand.query.filter_by(device_id=device_id, status='pendente').all()
    commands = [{"id": cmd.id, "command": cmd.command} for cmd in pending_commands]

    return jsonify({"status": "success", "pending_commands": commands})

# Rota para atualizar o status de um comando enviado
@device_routes.route('/update_command_status', methods=['POST'])
def update_command_status():
    """
    Atualiza o status do comando e armazena a resposta do dispositivo.
    """
    data = request.json
    command_id = data.get("command_id")
    status = data.get("status")
    response = data.get("response", None)

    if not command_id or not status:
        return jsonify({"status": "error", "message": "Campos command_id e status são obrigatórios"}), 400

    command = PendingCommand.query.get(command_id)
    if not command:
        return jsonify({"status": "error", "message": "Comando não encontrado"}), 404

    command.status = status
    command.response = response
    db.session.commit()

    return jsonify({"status": "success", "message": "Status do comando atualizado com sucesso"})