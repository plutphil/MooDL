import requests
import hashlib
import json
import os
class MoodleApiClient:
    def __init__(self, base_url, uname=None,pw=None):
        self.base_url = base_url
        self.token = ""
        if(uname!=None and pw != None):
            self.token = self.getToken(uname,pw)["token"]
        self.default_params = {
            "wstoken": self.token,
            "moodlewsrestformat": "json"
        }
    def login(self,uname=None,pw=None):
        if(uname!=None and pw != None):
            self.token = self.getToken(uname,pw)["token"]
            return self.token
    def getToken(self,uname, pw):
        url = self.base_url+"/login/token.php"
        params = {
            "username":uname,
            "password":pw,
            "service":"moodle_mobile_app"
        }
        res = requests.get(url,params=params)
        return res.json()
    def get(self, ws_function, additional_params=None):
        """
        Make a request to the Moodle API.

        :param ws_function: The Moodle Web Service function to call.
        :param additional_params: Additional parameters specific to the API function.
        :return: The response from the API in JSON format.
        """
        fileName = ws_function+"_"+hashlib.md5(json.dumps(additional_params).encode()).hexdigest()+".json"
        filePath = "cache/"+fileName
        os.makedirs("cache",exist_ok=True)
        if os.path.exists(filePath):
            with open(filePath,"r") as fd:
                return json.load(fd)
        params = self.default_params.copy()
        params["wsfunction"] = ws_function

        if additional_params:
            params.update(additional_params)
        url = self.base_url+"/webservice/rest/server.php"
        print(url,params)
        response = requests.get(url, params=params)

        # Check if the request was successful (status code 200)
        if response.status_code == 200:
            j = response.json()
            with open(filePath,"w") as fd:
                json.dump(j,fd)
            return j
        else:
            # If the request was not successful, raise an exception
            response.raise_for_status()
    def getContents(self,id):
        return self.get("core_course_get_contents",{"courseid": id})
    def getEnrolledCoursesByTimelineClassification(self,classification="all"):
        return self.get("core_course_get_enrolled_courses_by_timeline_classification",{"classification": classification})
    def getCourseModule(self,id):
        #return self.get("core_course_get_course_module_by_instance",{"module" : str(id), "instance" : int(id)})
        #return self.get("core_course_get_module",{"cmid":id,"sectionreturn":1})
        return self.get("core_course_get_course_module",{"cmid":id})
    def getCourseModuleInstance(self,module,instance):
        return self.get("core_course_get_course_module_by_instance",{"module" : module, "instance" : instance})
    def getModule(self,cmid,sectionreturn):
        return self.get("core_course_get_module",{"cmid":cmid,"sectionreturn":sectionreturn})
    def getAllResources(self):
        return self.get("mod_resource_get_resources_by_courses",{})
    def getAllResourcesByCourse(self,course):
        return self.get("mod_resource_get_resources_by_courses",{"courseids[0]": id})
    def getAllResourcesByCourse(self,ids):
        return self.get("mod_resource_get_resources_by_courses",{"courseids[]": ids})
    def getUrlsByCourse(self, id):
        return self.get("mod_url_get_urls_by_courses",{"courseids[0]": id})
    def getUrlsByCourses(self, ids=[]):
        return self.get("mod_url_get_urls_by_courses",{"courseids[]": ids})