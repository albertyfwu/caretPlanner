import webapp2
import os
import jinja2

from google.appengine.api import users

from apiclient.discovery import build

jinja_environment = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname
(__file__)))

class MainPage(webapp2.RequestHandler):
    def get(self):
        user = users.get_current_user()
        
        if user:
            template_values = {
                'username': user.nickname(),
                'logOutUrl': users.create_logout_url("/")
            }
            
            template = jinja_environment.get_template('index.html')
            self.response.out.write(template.render(template_values))
        else:
            self.redirect(users.create_login_url(self.request.uri))

app = webapp2.WSGIApplication([('/', MainPage)],
                              debug=True)
