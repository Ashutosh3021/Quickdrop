import uuid
import time
from config import SESSION_TTL


active_sessions = {}
active_transfers = {}


def create_session(files_metadata):
    session_id = str(uuid.uuid4())
    active_sessions[session_id] = {
        'id': session_id,
        'files': files_metadata,
        'state': 'CREATED',
        'created_at': time.time(),
        'receiver_connected': False,
        'sender_confirmed': False
    }
    return session_id


def get_session(session_id):
    session = active_sessions.get(session_id)
    if session and time.time() - session['created_at'] < SESSION_TTL:
        return session
    return None


def update_session_state(session_id, state):
    if session_id in active_sessions:
        active_sessions[session_id]['state'] = state


def set_receiver_connected(session_id):
    if session_id in active_sessions:
        active_sessions[session_id]['receiver_connected'] = True
        active_sessions[session_id]['state'] = 'RECEIVER_JOINED'


def set_sender_confirmed(session_id):
    if session_id in active_sessions:
        active_sessions[session_id]['sender_confirmed'] = True
        active_sessions[session_id]['state'] = 'SENDER_CONFIRMED'


def set_transferring(session_id):
    if session_id in active_sessions:
        active_sessions[session_id]['state'] = 'TRANSFERRING'


def set_complete(session_id):
    if session_id in active_sessions:
        active_sessions[session_id]['state'] = 'COMPLETE'


def delete_session(session_id):
    if session_id in active_sessions:
        del active_sessions[session_id]
    if session_id in active_transfers:
        del active_transfers[session_id]


def expire_sessions():
    current_time = time.time()
    expired = [
        sid for sid, sess in active_sessions.items()
        if current_time - sess['created_at'] >= SESSION_TTL
    ]
    for sid in expired:
        delete_session(sid)
    return len(expired)
