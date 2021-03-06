from django import template

register = template.Library()


@register.tag
def current_nav(parser, token):
    args = token.split_contents()
    template_tag = args[0]
    if len(args) < 2:
        msg = "%r tag requires at least one argument" % template_tag
        raise template.TemplateSyntaxError(msg)
    return NavSelectedNode(args[1])


class NavSelectedNode(template.Node):
    def __init__(self, url):
        self.url = url

    def render(self, context):
        path = context['request'].path
        pValue = template.Variable(self.url).resolve(context)
        if (pValue == '/' or pValue == '') and not (path == '/' or path == ''):
            return ""
        if path.startswith(pValue):
            return 'active'
        return ""
