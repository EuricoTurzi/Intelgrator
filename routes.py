from flask import Blueprint, request, jsonify
from models import db, DeviceData, NeighborCell, PendingCommand, DeviceConfig
from flask_socketio import emit
from datetime import datetime
import json

device_routes = Blueprint('device_routes', __name__)

@device_routes.route('/receive_data', methods=['POST'])
def receive_data():
    data = request.json  # Espera dados JSON
    print(f"Dados recebidos na rota '/receive_data': {data}")

    # Validação: verificar se há exatamente 6 células vizinhas
    neighbor_cells_data = data.get('neighbor_cells', [])
    if len(neighbor_cells_data) != 6:
        print("Erro: Exatamente 6 células vizinhas são necessárias")
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
        print(f"Criado novo DeviceData para device_id {data['device_id']}")
    else:
        # Atualiza o registro existente
        for key, value in data.items():
            if hasattr(device_data, key) and key != 'neighbor_cells':
                setattr(device_data, key, value)
        print(f"Atualizado DeviceData existente para device_id {data['device_id']}")

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
    try:
        db.session.commit()
        print("Dados do dispositivo e células vizinhas salvos com sucesso")
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao salvar dados: {e}")
        return jsonify({'status': 'error', 'message': 'Erro ao salvar dados'}), 500

    return jsonify({'status': 'success', 'message': 'Dados processados com sucesso'})

# Rota para obter os dados mais recentes de cada dispositivo
@device_routes.route('/latest_data', methods=['GET'])
def get_latest_data():
    subquery = db.session.query(
        DeviceData.device_id,
        db.func.max(DeviceData.created_at).label('max_created_at')
    ).group_by(DeviceData.device_id).subquery()

    devices = db.session.query(DeviceData).join(
        subquery,
        (DeviceData.device_id == subquery.c.device_id) & 
        (DeviceData.created_at == subquery.c.max_created_at)
    ).all()

    if not devices:
        print("Nenhum dado disponível")
        return jsonify({"status": "error", "message": "Nenhum dado disponível"}), 404

    data = [device.to_dict() for device in devices]

    return jsonify(data), 200

# Rota para enviar comandos ao dispositivo e salvar no banco
@device_routes.route('/send_command', methods=['POST'])
def send_command():
    data = request.json
    device_id = data.get("device_id")
    command_type = data.get("command_type")

    if not device_id or not command_type:
        print("Erro: Campos device_id e command_type são obrigatórios")
        return jsonify({"status": "error", "message": "Campos device_id e command_type são obrigatórios"}), 400

    command_map = {
        "ReqICCID": f"ST410CMD;{device_id};02;ReqICCID\n",
        "StartEmg": f"ST410CMD;{device_id};02;StartEmg\n",
        "StopEmg": f"ST410CMD;{device_id};02;StopEmg\n",
        "Preset": f"ST410CMD;{device_id};02;Preset\n",
    }

    command = command_map.get(command_type)
    if not command:
        print("Erro: Comando inválido")
        return jsonify({"status": "error", "message": "Comando inválido"}), 400

    # Salva o comando como pendente no banco de dados
    pending_command = PendingCommand(device_id=device_id, command=command)
    db.session.add(pending_command)
    db.session.commit()
    print(f"Comando '{command_type}' salvo e aguardando envio para device_id {device_id}")

    return jsonify({"status": "success", "message": "Comando salvo e aguardando envio"}), 200

# Rota para verificar comandos pendentes para um dispositivo específico
@device_routes.route('/check_pending_commands', methods=['GET'])
def check_pending_commands():
    """
    Verifica comandos pendentes para o dispositivo especificado.
    """
    device_id = request.args.get('device_id')
    if not device_id:
        print("Erro: device_id é obrigatório")
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
    print(f"Dados recebidos na rota '/update_command_status': {data}")
    command_id = data.get("command_id")
    status = data.get("status")
    response_text = data.get("response", None)

    if not command_id or not status:
        print("Erro: Campos command_id e status são obrigatórios")
        return jsonify({"status": "error", "message": "Campos command_id e status são obrigatórios"}), 400

    command = PendingCommand.query.get(command_id)
    if not command:
        print(f"Erro: Comando com ID {command_id} não encontrado")
        return jsonify({"status": "error", "message": "Comando não encontrado"}), 404

    command.status = status
    command.response = response_text
    try:
        db.session.commit()
        print(f"Status do comando ID {command_id} atualizado para '{status}'")
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao atualizar status do comando: {e}")
        return jsonify({"status": "error", "message": "Erro ao atualizar status do comando"}), 500

    return jsonify({"status": "success", "message": "Status do comando atualizado com sucesso"})

@device_routes.route('/update_device_config', methods=['POST'])
def update_device_config():
    data = request.json
    print(f"Dados recebidos na rota '/update_device_config': {data}")
    device_id = data.get('device_id')
    config_data = data.get('config_data')

    if not device_id or not config_data:
        print("Erro: Campos device_id e config_data são obrigatórios")
        return jsonify({"status": "error", "message": "Campos device_id e config_data são obrigatórios"}), 400

    device_config = DeviceConfig.query.filter_by(device_id=device_id).first()
    if not device_config:
        device_config = DeviceConfig(device_id=device_id)
        db.session.add(device_config)
        print(f"Criado novo DeviceConfig para device_id {device_id}")
    else:
        print(f"Atualizando DeviceConfig existente para device_id {device_id}")

    # Atualiza as configurações
    device_config.ntw_config = config_data.get('NTW')
    device_config.tim_config = config_data.get('TIM')
    device_config.npt_config = config_data.get('NPT')
    device_config.pfc_config = config_data.get('PFC')
    device_config.pdl_config = config_data.get('PDL')
    device_config.gps_config = config_data.get('GPS')
    device_config.last_updated = datetime.utcnow()

    print(f"DeviceConfig atualizado: {device_config.to_dict()}")

    try:
        db.session.commit()
        print("Configurações salvas com sucesso no banco de dados")
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao salvar configurações: {e}")
        return jsonify({"status": "error", "message": "Erro ao salvar configurações"}), 500

    return jsonify({"status": "success", "message": "Configurações atualizadas com sucesso"}), 200

@device_routes.route('/get_device_config/<device_id>', methods=['GET'])
def get_device_config(device_id):
    device_config = DeviceConfig.query.filter_by(device_id=device_id).first()
    if not device_config:
        print(f"Configurações não encontradas para device_id {device_id}")
        return jsonify({"status": "error", "message": "Configurações não encontradas"}), 404

    return jsonify({"status": "success", "config": device_config.to_dict()}), 200

# Rota para obter o comando pendente pelo device_id e command_type
@device_routes.route('/get_command_by_device_and_type', methods=['GET'])
def get_command_by_device_and_type():
    device_id = request.args.get('device_id')
    command_type = request.args.get('command_type')

    if not device_id or not command_type:
        print("Erro: Campos device_id e command_type são obrigatórios")
        return jsonify({"status": "error", "message": "Campos device_id e command_type são obrigatórios"}), 400

    command_string = f"ST410CMD;{device_id};02;{command_type}\n"

    command = PendingCommand.query.filter(
        PendingCommand.device_id == device_id,
        PendingCommand.command.like(f"%{command_type}%"),
        PendingCommand.status == 'pendente'
    ).order_by(PendingCommand.created_at.desc()).first()

    if command:
        print(f"Comando encontrado: ID {command.id}")
        return jsonify({"status": "success", "command": {"id": command.id, "command": command.command}})
    else:
        print(f"Erro: Comando não encontrado para device_id {device_id} e command_type {command_type}")
        return jsonify({"status": "error", "message": "Comando não encontrado"}), 404
