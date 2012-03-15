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
                'username': user.nickname(),
                'signOutUrl': users.create_logout_url("/")
            }
            
            template = jinja_environment.get_template('index.html')
            self.response.out.write(template.render(template_values))
        else:
            self.redirect(users.create_login_url(self.request.uri))
    def post(self):
#        name = self.request.get('name')
#        time = self.request.get('time')
#        self.response.out.write(name + ' ' + time)
        text = self.request.get('text')
        self.response.out.write(text + ' was typed')
        
class AboutPage(webapp2.RequestHandler):
    def get(self):
        self.response.out.write(jinja_environment.get_template('about.html').render({}));

app = webapp2.WSGIApplication([('/', MainPage),
                               ('/about', AboutPage)],
                              debug=True)
