import webapp2
import os
import jinja2

from google.appengine.api import users
import json
import re

import httplib2
import logging
import os
import pickle

jinja_environment = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname
(__file__)))

contacts = ['al', 'albert', 'alex', 'alexander', 'alexandra', 'a', 'as', 'asd', 'asdf']

class MainHandler(webapp2.RequestHandler):
    def get(self):
        user = users.get_current_user()        
        if user:
            template_values = {
                'username': user.nickname(),
                'signOutUrl': users.create_logout_url("/")
            }
            
            template = jinja_environment.get_template('index.html')
            self.response.out.write(template.render(template_values))
        else:
            self.redirect(users.create_login_url(self.request.uri))
    def post(self):
        query = self.request.get('query')
        regex = '^' + query + '.*$'
        matches = [name for name in contacts if re.match(regex, name)]
        
        self.response.headers['Content-Type'] = 'application/json'
        result = json.dumps({'matches':matches})
        self.response.out.write(result)
        
class TestApiHandler(webapp2.RequestHandler):
    def get(self):
        pass
        
class AboutHandler(webapp2.RequestHandler):
    def get(self):
        self.response.out.write(jinja_environment.get_template('about.html').render({}))

class TestHandler(webapp2.RequestHandler):
    def get(self):
        self.response.out.write(jinja_environment.get_template('google252010397c396386.html').render({}))

app = webapp2.WSGIApplication([('/', MainHandler),
                               ('/google252010397c396386.html', TestHandler),
                               ('/api', TestApiHandler),
                               ('/about', AboutHandler)],
                              debug=True)

def main():
    webapp2.util.run_wsgi_app(app)
    
if __name__ == '__main__':
    main()
