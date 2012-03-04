import webapp2

class MainPage(webapp2.RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'text/plain'
        self.response.out.write('Hello, world!')

app = webapp2.WSGIApplication([('/', MainPage)],
                              debug=True)

## Test line for commit from ragtz
