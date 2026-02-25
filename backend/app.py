import os
import threading
import time
import io
import qrcode
from flask import Flask, render_template, request, jsonify, Response, send_from_directory
from flask_socketio import SocketIO, join_room, emit
from werkzeug.utils import secure_filename
from urllib.parse import unquote

from config import PORT, CHUNK_SIZE
from utils.network import get_local_ip
from utils.session import (
    create_session, get_session, update_session_state,
    set_receiver_connected, set_sender_confirmed, set_transferring,
    set_complete, delete_session, expire_sessions, active_sessions
)
from utils.file_handler import stream_file, compute_checksum


app = Flask(__name__, template_folder='../frontend/templates', static_folder='../frontend/static')
app.config['SECRET_KEY'] = 'multishare-secret'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


@app.route('/')
def index():
    return render_template('index.html', ip=get_local_ip(), port=PORT)


@app.route('/send')
def send_page():
    session_id = request.args.get('session')
    return render_template('send.html', session_id=session_id, ip=get_local_ip(), port=PORT)


@app.route('/receive')
def receive_page():
    session_id = request.args.get('session')
    return render_template('receive.html', session_id=session_id, ip=get_local_ip(), port=PORT)


@app.route('/api/create-receive-session', methods=['POST'])
def create_receive_session():
    session_id = create_session({})
    share_url = f"http://{get_local_ip()}:{PORT}/send?session={session_id}"
    qr_url = f"http://{get_local_ip()}:{PORT}/api/qr/{session_id}"
    
    return jsonify({
        'session_id': session_id,
        'share_url': share_url,
        'qr_url': qr_url
    })


@app.route('/manifest.json')
def manifest():
    return send_from_directory('../frontend/static', 'manifest.json')


@app.route('/sw.js')
def service_worker():
    return send_from_directory('../frontend/static', 'sw.js')


@app.route('/icons/<path:filename>')
def icons(filename):
    return send_from_directory('../frontend/static/icons', filename)


@app.route('/api/create-session', methods=['POST'])
def create_session_api():
    files = request.files.getlist('files')
    existing_session_id = request.form.get('session_id')
    files_metadata = {}
    
    for f in files:
        if f.filename:
            filename = secure_filename(f.filename)
            filepath = os.path.join(BASE_DIR, 'uploads', filename)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            f.save(filepath)
            file_size = os.path.getsize(filepath)
            files_metadata[filename] = {
                'filepath': filepath,
                'size': file_size,
                'checksum': compute_checksum(filepath) if file_size > 0 else ''
            }
    
    if existing_session_id and existing_session_id != 'None':
        session_id = existing_session_id
        session = get_session(session_id)
        if not session:
            session_id = create_session(files_metadata)
            share_url = None
        else:
            session['files'].update(files_metadata)
            share_url = None
    elif files_metadata:
        session_id = create_session(files_metadata)
        share_url = f"http://{get_local_ip()}:{PORT}/receive?session={session_id}"
    else:
        return jsonify({'error': 'No files selected'}), 400
    
    return jsonify({
        'session_id': session_id,
        'share_url': share_url,
        'files': [{'name': k, 'size': v['size'], 'checksum': v['checksum']} for k, v in files_metadata.items()]
    })


@app.route('/api/qr/<session_id>')
def qr_code(session_id):
    session = get_session(session_id)
    if not session:
        return jsonify({'error': 'Session expired'}), 404
    
    # QR contains /send?session=xxx (for phone to scan and send files to PC)
    share_url = f"http://{get_local_ip()}:{PORT}/send?session={session_id}"
    qr = qrcode.QRCode(box_size=10, border=2)
    qr.add_data(share_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buf = io.BytesIO()
    img.save(buf, 'PNG')
    buf.seek(0)
    
    return Response(buf.getvalue(), mimetype='image/png')


@app.route('/api/session/<session_id>')
def get_session_api(session_id):
    session = get_session(session_id)
    if not session:
        return jsonify({'error': 'Session not found or expired'}), 404
    
    return jsonify({
        'id': session['id'],
        'state': session['state'],
        'files': [{'name': k, 'size': v['size'], 'checksum': v['checksum']} for k, v in session['files'].items()]
    })


@app.route('/download/<session_id>/<filename>')
def download_file(session_id, filename):
    filename = unquote(filename)
    session = get_session(session_id)
    if not session or filename not in session['files']:
        return jsonify({'error': 'File not found'}), 404
    
    file_info = session['files'][filename]
    filepath = file_info['filepath']
    
    return Response(
        stream_file(filepath),
        mimetype='application/octet-stream',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Content-Length': file_info['size']
        }
    )


@socketio.on('pair_request')
def handle_pair(data):
    session_id = data.get('session_id')
    session = get_session(session_id)
    if session:
        join_room(session_id)
        set_receiver_connected(session_id)
        emit('receiver_ready', {'session_id': session_id}, room=session_id)


@socketio.on('sender_confirm')
def handle_confirm(data):
    session_id = data.get('session_id')
    session = get_session(session_id)
    if session:
        set_sender_confirmed(session_id)
        set_transferring(session_id)
        emit('transfer_starting', {
            'session_id': session_id,
            'files': [{'name': k, 'size': v['size'], 'checksum': v['checksum']} for k, v in session['files'].items()]
        }, room=session_id)


@socketio.on('transfer_progress')
def handle_progress(data):
    emit('transfer_progress', data, room=data.get('session_id'))


@socketio.on('transfer_complete')
def handle_complete(data):
    session_id = data.get('session_id')
    set_complete(session_id)
    emit('transfer_complete', {'session_id': session_id}, room=session_id)


def cleanup_loop():
    while True:
        expire_sessions()
        time.sleep(60)


if __name__ == '__main__':
    threading.Thread(target=cleanup_loop, daemon=True).start()
    
    local_ip = get_local_ip()
    print(f"🚀 MultiShare starting...")
    print(f"📱 Open on sender:   http://{local_ip}:{PORT}")
    print(f"📥 Receiver visits: http://{local_ip}:{PORT}")
    
    socketio.run(app, host='0.0.0.0', port=PORT, debug=False)
