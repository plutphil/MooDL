from flask import Flask, jsonify, Response, render_template, request, redirect, url_for,send_from_directory
import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import os
from MoodleApiClient import MoodleApiClient
import threading
import time
import queue
app = Flask(__name__)
client = MoodleApiClient("")
IMAGE_FOLDER = os.path.join(app.static_folder, 'images')
app.config['IMAGE_FOLDER'] = IMAGE_FOLDER

if not os.path.exists(IMAGE_FOLDER):
    os.makedirs(IMAGE_FOLDER)
os.makedirs(IMAGE_FOLDER,exist_ok=True)
os.makedirs("config",exist_ok=True)
os.makedirs("cache",exist_ok=True)

app.config['COURSE_DATA_FILE'] = 'config/course_data.json'
courses=[]
allurls=[]

clients = []
eventqueue = queue.Queue()

stop_background_thread = False

def save_course_data():
    with open(app.config['COURSE_DATA_FILE'], 'w') as file:
        json.dump(courses, file)

# Function to load course data from a JSON file
def load_course_data():
    if os.path.exists(app.config['COURSE_DATA_FILE']):
        with open(app.config['COURSE_DATA_FILE'], 'r') as file:
            return json.load(file)
    return []
courses = load_course_data()
coursebyid={}
def getCourseById(id):
    if id in coursebyid:
        return coursebyid[id]
    for i in courses:
        if i["id"]==id:
            coursebyid[id]=i
            return i
@app.route('/')
def index():
    return render_template('index.html')
def downloadimg(id,url):
    image_filename = f"{id}_image.jpg"
    image_path = os.path.join(app.config['IMAGE_FOLDER'], image_filename)
    if not os.path.exists(image_path):
        response = requests.get(url)
        with open(image_path, 'wb')     as img_file:
            img_file.write(response.content)
    return image_filename
@app.route('/login', methods=['POST'])
def login():
    global courses,client,allurls
    username = request.form['username']
    password = request.form['password']
    baseurl = request.form['baseurl']

    # Perform login using your existing code
    # ...
    client = MoodleApiClient(baseurl,username, password)
    
    #j = moodlelogin.login(username,password)
    #courses =  j[0]["data"]['courses']
    j = client.getEnrolledCoursesByTimelineClassification()
    
    #if not "courses" in j:
    #    print(j)
    #    return j
    courses =  j['courses']
    courseids = []
    for course in courses:
        course["formatted_startdate"] = datetime.utcfromtimestamp(course["startdate"]).strftime('%Y-%m-%d %H:%M:%S')
        courseids.append(course["id"])
    urls = client.getUrlsByCourses(courseids)
    print(urls)
    
    allurls = urls["urls"]
    for modurl in urls["urls"]:
        course = getCourseById(modurl["course"])
        if not "urls" in course:
            course["urls"]=[]
        if not "urlsbyid" in course:
            course["urlsbyid"]={}
        course["urls"].append(modurl)
        course["urlsbyid"][modurl["id"]]=modurl
    for course in courses:
        if course['courseimage'].startswith('http'):
            course['local_image_path'] = downloadimg(course['id'],course['courseimage'])
    save_course_data()
    # After successful login, redirect to the dashboard
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html', courses=courses)
def downloadresource(resource_info,coursename):
    if not "contents" in resource_info:
        print(resource_info)
        return
    contents = resource_info['contents']

    # Create a folder to save the downloaded files
    folder_path = f"static/resources/{coursename}"
    os.makedirs(folder_path, exist_ok=True)

    for content in contents:
        if content['type'] == 'file':
            file_url = content['fileurl']
            file_name = content['filename']
            file_path = os.path.join(folder_path, file_name)
            
            mimetype = content["mimetype"]
            
            if mimetype.startswith("video/"):
                continue
            if mimetype.startswith("audio/"):
                continue
            
            if os.path.exists(file_path):
                content["staticurl"] = os.path.join(f"/resources",coursename ,file_name)
                continue
            if client.token=="":
                continue
            # Download the file
            def downloadthread(file_url,file_path):
                file_response = requests.get(file_url,params={"token":client.token})
                if file_response.headers._store["content-type"][1].startswith("application/json"):
                    return "failed"
                if file_response.status_code!=200:
                    return
                with open(file_path, 'wb') as file:
                    file.write(file_response.content)
            threading.Thread(target=downloadthread,args=(file_url,file_path)).start()
            
            content["staticurl"] = os.path.join(f"/resources",coursename, file_name)
            print(f"Downloaded: {file_name} to {file_path}")

@app.route('/c/<int:course_id>')
def course_page(course_id):
    # Retrieve the course data based on the provided course_id
    course = client.getContents(course_id)
    courseurls = client.getUrlsByCourse(course_id)
    courseurlsbyid = {}
    current_course = getCourseById(course_id)
    for u in courseurls["urls"]:
        courseurlsbyid[u["id"]]=u
    modnames = []
    try:
        with open("modnames.json","r") as fd:
            modnames = json.load(fd)
    except:
        pass
    for section in course:
        for module in section["modules"]:
            
            if module["instance"] in courseurlsbyid:
                module["modurl"]=courseurlsbyid[module["instance"]]
                pass
            elif module["modname"]=="resource" or module["modname"]=="folder":
                pass
                
                if downloadresource(module,current_course["shortname"])=="failed":
                    pass
            elif not (module["modname"] in modnames):
                print("unknown modname",module["modname"],module['modplural'])
                modnames.append(module["modname"])
                with open("modnames.json","w") as fd:
                    json.dump(modnames,fd)
            else:
                #
                pass
    if course:
            return render_template('course_page.html', data=course,course=getCourseById(int(course_id)))
    else:
        return "Course not found", 404
    
@app.route('/images/<filename>')
def serve_image(filename):
    return send_from_directory(app.config['IMAGE_FOLDER'], filename)
@app.route('/resources/<foldername>/<filename>')
def serve_resources(foldername,filename):
    return send_from_directory(os.path.join(app.static_folder,"resources",foldername), filename)
# Function to get a unique response object for each client
def get_response_object():
    return jsonify({"id": len(clients), "data": "Connected to SSE"})
@app.route('/stream')
def stream():
    respobj = get_response_object()
    def event_stream():
        # Add the client to the list
        clients.append({"id": len(clients) + 1, "response": None})

        # Assign the current response object to the client
        client_id = len(clients)
        clients[client_id - 1]["response"] = respobj
        #app.app_context().push()
        message = f"Update from server: {time.strftime('%H:%M:%S')}"
        time.sleep(1)
        #yield f"data: {message}\r\n"
        yield "data:"+json.dumps({"id":1,"data":"HELLO"})+"\n\n"
        index = 0
        try:
            while True:
                try:
                    ev = eventqueue.get(True,5)
                    message = json.dumps({"id":index,"data":"HELLO","mesg":ev})
                    yield f"data:{message}"+"\n\n"
                    index+=1
                except Exception as e:
                    print(e)
                    pass
        except GeneratorExit:
            # Remove the client when the connection is closed
            clients.pop(client_id - 1)

    return Response(event_stream(), content_type='text/event-stream')
def background_task():
    global stop_background_thread

    while not stop_background_thread:
        # Simulate some background process
        time.sleep(1)

        # Send SSE updates to all connected clients
        for client in clients:
            if client["response"]:
                message = f"Background update: {time.strftime('%H:%M:%S')}"
                eventqueue.put(message)
                #client["response"].write(f"data: {message}\n\n")
                #client["response"].flush()
@app.route('/ssetest')
def ssetest():
    return render_template('ssetest.html')
@app.route('/start_background_thread')
def start_background_thread():
    # Start the background thread
    background_thread = threading.Thread(target=background_task)
    background_thread.start()

    return "Background thread started."
def shutdown_hook():
    global stop_background_thread
    stop_background_thread = True
if __name__ == '__main__':
    #app.teardown_appcontext(shutdown_hook)
    
    app.run(debug=True)
