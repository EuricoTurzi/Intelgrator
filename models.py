from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

# Modelo para armazenar os dados do dispositivo
class DeviceData(db.Model):
    __tablename__ = 'device_data'
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(20), nullable=False)
    sw_version = db.Column(db.String(10))
    model = db.Column(db.String(10))
    cell_id = db.Column(db.String(10))
    mcc = db.Column(db.String(5))
    mnc = db.Column(db.String(5))
    rx_lvl = db.Column(db.String(5))
    lac = db.Column(db.String(10))
    tm_adv = db.Column(db.String(5))
    backup_voltage = db.Column(db.Float)
    online_status = db.Column(db.Boolean)
    message_number = db.Column(db.Integer)
    mode = db.Column(db.String(5))
    col_net_rf_ch = db.Column(db.String(5))
    gps_date = db.Column(db.Date)
    gps_time = db.Column(db.Time)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    speed = db.Column(db.Float)
    course = db.Column(db.Float)
    satt = db.Column(db.Integer)  # Número de satélites
    gps_fix = db.Column(db.Boolean)
    temperature = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    neighbor_cells = db.relationship('NeighborCell', backref='device_data', cascade="all, delete-orphan")
    
    def to_dict(self):
        return {
            "device_id": self.device_id,
            "backup_voltage": self.backup_voltage,
            "online_status": self.online_status,
            "mode": self.mode,
            "gps_date": self.gps_date.isoformat() if self.gps_date else None,
            "gps_time": self.gps_time.strftime("%H:%M:%S") if self.gps_time else None,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "gps_fix": self.gps_fix,
            # Inclua outros campos, se necessário
        }

# Modelo para armazenar informações das células vizinhas
class NeighborCell(db.Model):
    __tablename__ = 'neighbor_cells'
    id = db.Column(db.Integer, primary_key=True)
    device_data_id = db.Column(db.Integer, db.ForeignKey('device_data.id'))
    cell_id = db.Column(db.String(10))
    mcc = db.Column(db.String(5))
    mnc = db.Column(db.String(5))
    lac = db.Column(db.String(10))
    rx_lvl = db.Column(db.String(5))
    tm_adv = db.Column(db.String(5))

# Modelo para armazenar os comandos pendentes a serem enviados para o dispositivo
class PendingCommand(db.Model):
    __tablename__ = 'pending_commands'
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(20), nullable=False)
    command = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), default='pendente')  # Status: 'pendente', 'enviado', 'respondido'
    response = db.Column(db.String(200), nullable=True)  # Resposta do equipamento
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

class DeviceConfig(db.Model):
    __tablename__ = 'device_configs'
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(20), unique=True, nullable=False)
    ntw_config = db.Column(db.JSON)
    tim_config = db.Column(db.JSON)
    npt_config = db.Column(db.JSON)
    pfc_config = db.Column(db.JSON)
    pdl_config = db.Column(db.JSON)
    gps_config = db.Column(db.JSON)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "device_id": self.device_id,
            "ntw_config": self.ntw_config,
            "tim_config": self.tim_config,
            "npt_config": self.npt_config,
            "pfc_config": self.pfc_config,
            "pdl_config": self.pdl_config,
            "gps_config": self.gps_config,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None
        }