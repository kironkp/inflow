from django.contrib import admin

from .models import Flowchart, Node, NodeLog, Tag

admin.site.register(Flowchart)
admin.site.register(Node)
admin.site.register(NodeLog)
admin.site.register(Tag)
