import webapp2
import os
import jinja2

from google.appengine.api import users
from google.appengine.ext import webapp
import json
import re

import logging

import httplib2


#import apiclient.discovery

#from apiclient.discovery import build

jinja_environment = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname
(__file__)))

contacts = ['al', 'albert', 'alex', 'alexander', 'alexandra', 'a', 'as', 'asd', 'asdf']

class MainPage(webapp2.RequestHandler):
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
        self.response.out.write(result);
        
class AboutPage(webapp2.RequestHandler):
    def get(self):
        self.response.out.write(jinja_environment.get_template('about.html').render({}));

app = webapp2.WSGIApplication([('/', MainPage),
                               ('/about', AboutPage)],
                              debug=True)

def main():
    webapp.util.run_wsgi_app(app)
    
if __name__ == '__main__':
    main()
