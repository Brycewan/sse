from flask import Flask, request, redirect, url_for, render_template, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, render_template, request, redirect, url_for, session
from flask_socketio import SocketIO, emit, join_room, leave_room
from datetime import datetime

app = Flask(__name__)
socketio = SocketIO(app)

app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres@localhost:5432/postgres'
app.config['SECRET_KEY'] = 'your_secret_key'
db = SQLAlchemy(app)

# database models
class Users(db.Model):
    username = db.Column(db.String(80), primary_key=True)
    password = db.Column(db.String(80), nullable=False)

class Friendships(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(80), db.ForeignKey('users.username'), nullable=False)
    friend_id = db.Column(db.String(80), db.ForeignKey('users.username'), nullable=False)
    status = db.Column(db.Boolean, default=False)

class FriendRequests(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_username = db.Column(db.String(80), nullable=False)
    receiver_username = db.Column(db.String(80), nullable=False)
    status = db.Column(db.String(20), default='pending')

class Room(db.Model):
    room_id = db.Column(db.Integer, primary_key=True)
    room_name = db.Column(db.String(80), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

class RoomMember(db.Model):
    user_id = db.Column(db.String(80), db.ForeignKey('users.username'), primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('room.room_id'), primary_key=True)

class RoomMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('room.room_id'), nullable=False)
    sender_id = db.Column(db.String(80), db.ForeignKey('users.username'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    sent_at = db.Column(db.DateTime, server_default=db.func.current_timestamp())


@app.route('/')
def index():
    # if 'user_id' in session:
    #     user = Users.query.get(session['user_id'])
    #     return render_template('index.html', logged_in=True, username=user.username)
    if 'username' in session:
        return render_template('index.html', logged_in=False, username=session['username'])
    else:
        return render_template('index.html', logged_in=False)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        # hashed_password = generate_password_hash(password)
        new_user = Users(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = Users.query.filter_by(username=username).first()
        # if user and check_password_hash(user.password, password):
        if user and user.password == password:
            session['username'] = user.username
            return redirect(url_for('info'))
        else:
            return 'Invalid username or password'
    return render_template('login.html')

@app.route('/info')
def info():
    if 'username' in session:
        username = session['username']
        friend_requests = get_friend_requests(username)
        friends = get_friends(username)
        rooms = get_rooms(username)

        info_data = {
            'username': username,
            'friend_requests': friend_requests,
            'friends': friends,
            'rooms': rooms
        }
        return render_template("info.html", info_data=info_data)
    else:
        return render_template('login.html')
    
def get_friends(username):
    user = Users.query.filter_by(username=username).first()
    if user:
        friend_list = Friendships.query.filter_by(user_id=username, status=True).all()
        return [friend.friend_id for friend in friend_list]
    return []

def get_friend_requests(username):
    user = Users.query.filter_by(username=username).first()
    if user:
        return FriendRequests.query.filter_by(receiver_username=username).all()
    return []

def get_rooms(username):
    user = Users.query.filter_by(username=username).first()
    if user:
        rooms = db.session.query(
            Room.room_id, 
            Room.room_name, 
            Room.created_at
        ).join(RoomMember, RoomMember.room_id == Room.room_id)\
         .filter(RoomMember.user_id == username).all()
        rooms_list = [{
            'room_id': room_id, 
            'room_name': room_name, 
            'created_at': created_at.strftime('%Y-%m-%d %H:%M:%S')  # 格式化日期时间
        } for room_id,room_name, created_at in rooms]
        return rooms_list
    return []

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('index'))

@app.route('/add_friend', methods=['POST'])
def add_friend():
    if 'username' in session:
        sender_username = session['username']
        receiver_username = request.form['friend_username']
        friend = Users.query.filter_by(username=receiver_username).first()
        if friend:
            # check if the friendship already exists
            existing_friendship = Friendships.query.filter_by(user_id=sender_username, friend_id=receiver_username, status=True).first()
            existing_request = FriendRequests.query.filter_by(sender_username=sender_username, receiver_username=receiver_username).first()
            if existing_friendship:
                print(Friendships.user_id, Friendships.friend_id, sender_username, receiver_username, Friendships.status)
                return 'Already friends'
            elif existing_request:
                return 'Friend request already sent'
            else:
                # create a friend request
                friend_request = FriendRequests(sender_username=sender_username, receiver_username=receiver_username)
                db.session.add(friend_request)
                db.session.commit()
                return redirect(url_for('info'))
        else:
            return 'User not found'
    else:
        return redirect(url_for('login'))

    
@app.route('/accept_request/<int:request_id>')
def accept_request(request_id):
    # return 'Accept request'
    friend_request = FriendRequests.query.get(request_id)
    if friend_request:
        sender_username = friend_request.sender_username
        receiver_username = friend_request.receiver_username
        # create two friendships
        friendship1 = Friendships(user_id=sender_username, friend_id=receiver_username, status=True)
        friendship2 = Friendships(user_id=receiver_username, friend_id=sender_username, status=True)
        # delete the friend request and add the friendships
        db.session.delete(friend_request)
        db.session.add(friendship1)
        db.session.add(friendship2)
        db.session.commit()
        return redirect(url_for('info'))
    else:
        return 'Friend request not found'

@app.route('/reject_request/<int:request_id>')
def reject_request(request_id):
    friend_request = FriendRequests.query.get(request_id)
    if friend_request:
        db.session.delete(friend_request)
        db.session.commit()
        return redirect(url_for('info'))
    else:
        return 'Friend request not found'
    
@app.route('/create_room', methods=['POST'])
def create_room():
    if 'username' in session:
        room_name = request.form['room_name']
        existing_room = Room.query.filter_by(room_name=room_name).first()
        if existing_room:
            return "Room name already taken"
        new_room = Room(room_name=room_name)
        db.session.add(new_room)
        db.session.commit()
        current_user_username = session.get('username')
        if current_user_username:
            current_user = Users.query.filter_by(username=current_user_username).first()
            if current_user:
                new_room_member = RoomMember(user_id=current_user.username, room_id=new_room.room_id)
                db.session.add(new_room_member)
                db.session.commit()
        return redirect(url_for('info'))
    else:
        return redirect(url_for('login'))

@app.route('/join', methods=['POST'])
def join():
    if 'username' in session:
        room_name = request.form.get('room_name')
        if room_name:
            existing_room = Room.query.filter_by(room_name=room_name).first()
            if existing_room:
                room_id = existing_room.room_id
                return redirect(url_for('chat', room_id=room_id, user_name=session.get('username')))
            else:
                return "Room does not exist", 404
        else:
            return "Room name is required", 400
    else:
        return redirect(url_for('login'))

@app.route('/chat/<room_id>/<user_name>')
def chat(room_id, user_name):
    room_name = get_room_name_by_id(room_id)
    chat_info = {
        'room_id': room_id,
        'room_name': room_name,
        'username': user_name
    }
    return render_template('chat.html', chat_info=chat_info)

def get_room_name_by_id(room_id):
    room = Room.query.filter_by(room_id=room_id).first()
    if room:
        return room.room_name
    else:
        return None

@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('join_room')
def handle_join_room(data):
    room_id = data['room_id']
    username = data['username']
    join_room(room_id) 
    history_messages = RoomMessage.query.filter_by(room_id=room_id).order_by(RoomMessage.sent_at.desc()).limit(5).all()
    history_messages.reverse()
    for message in history_messages:
        emit('message', {
            'user': message.sender_id,
            'text': message.content,
            'sent_at': message.sent_at.strftime('%Y-%m-%d %H:%M:%S')
        }, room=request.sid)
    room_name = get_room_name_by_id(room_id)
    emit('status', {'messages': f'{username} has joined the room {room_name}.'}, room=room_id, include_self=True)

@socketio.on('message')
def handle_message(data):
    room_id = data['room_id']
    sender_id = data['username']
    content = data['text']
    sent_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    new_message = RoomMessage(
        room_id=room_id,
        sender_id=sender_id,
        content=content,
    )

    db.session.add(new_message)
    db.session.commit()

    emit('message', {'user': sender_id, 'text': content, 'sent_at': sent_at}, room=room_id)

@socketio.on('leave_room')
def handle_leave_room(data):
    room_id = data['room_id']
    username = data['username']
    # 用户离开聊天室
    leave_room(room_id)
    # 向聊天室内的其他用户广播离开消息
    emit('status', {'messages': f'{username} has left the room.'}, room=room_id)

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)