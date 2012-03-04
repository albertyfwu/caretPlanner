import webapp2
import os
import jinja2

from google.appengine.api import users

jinja_environment = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname
(__file__)))

class MainPage(webapp2.RequestHandler):
    def get(self):
        
        
        user = users.get_current_user()
        
        if user:        
            template_values = {
                'username': user.nickname()
            }
            
            template = jinja_environment.get_template('index.html')
            self.response.out.write(template.render(template_values))
        else:
            self.redirect(users.create_login_url(self.request.uri))
        
#        user = users.get_current_user()
#
#        if user:
#            self.response.headers['Content-Type'] = 'text/plain'
#            self.response.out.write('Hello, ' + user.nickname())
#        else:
#            self.redirect(users.create_login_url(self.request.uri))

class TestPage(webapp2.RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'text/plain'
        self.response.out.write('testing')

app = webapp2.WSGIApplication([('/', MainPage),
                               ('/testing', TestPage)],
                              debug=True)
