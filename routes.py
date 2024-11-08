from flask import Blueprint, request, jsonify
from models import db, DeviceData, NeighborCell, PendingCommand
from flask_socketio import emit
from datetime import datetime

device_routes = Blueprint('device_routes', __name__)

@device_routes.route('/receive_data', methods=['POST'])
def receive_data():
    data = request.json  # Espera dados JSON

    # Validação: verificar se há exatamente 6 células vizinhas
    neighbor_cells_data = data.get('neighbor_cells', [])
    if len(neighbor_cells_data) != 6:
        return jsonify({'status': 'error', 'message': 'Exatamente 6 células vizinhas são necessárias'}), 400

    # Criação ou atualização do dispositivo
    device_data = DeviceData.query.filter_by(device_id=data['device_id']).first()
    if not device_data:
        # Cria novo registro para o dispositivo
        device_data = DeviceData(
            device_id=data['device_id'],
            sw_version=data['sw_version'],
            model=data['model'],
            cell_id=data['cell_id'],
            mcc=data['mcc'],
            mnc=data['mnc'],
            rx_lvl=data['rx_lvl'],
            lac=data['lac'],
            tm_adv=data['tm_adv'],
            backup_voltage=data['backup_voltage'],
            online_status=data['online_status'],
            message_number=data['message_number'],
            mode=data['mode'],
            col_net_rf_ch=data['col_net_rf_ch'],
            gps_date=data['gps_date'],
            gps_time=data['gps_time'],
            latitude=data['latitude'],
            longitude=data['longitude'],
            speed=data['speed'],
            course=data['course'],
            satt=data['satt'],
            gps_fix=data['gps_fix'],
            temperature=data['temperature']
        )
        db.session.add(device_data)
    else:
        # Atualiza o registro existente
        for key, value in data.items():
            if hasattr(device_data, key) and key != 'neighbor_cells':
                setattr(device_data, key, value)

        # Remove células vizinhas existentes
        NeighborCell.query.filter_by(device_data_id=device_data.id).delete()

    # Adiciona novas células vizinhas como instâncias do modelo NeighborCell
    for cell_data in neighbor_cells_data:
        neighbor_cell = NeighborCell(
            device_data_id=device_data.id,
            cell_id=cell_data['cell_id'],
            mcc=cell_data['mcc'],
            mnc=cell_data['mnc'],
            lac=cell_data['lac'],
            rx_lvl=cell_data['rx_lvl'],
            tm_adv=cell_data['tm_adv']
        )
        db.session.add(neighbor_cell)

    # Confirma todas as alterações no banco de dados
    db.session.commit()

    return jsonify({'status': 'success', 'message': 'Dados processados com sucesso'})

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