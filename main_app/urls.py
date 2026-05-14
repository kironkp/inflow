from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),

    path('flowcharts/', views.flowchart_index, name='flowchart-index'),
    path('flowcharts/create/', views.FlowchartCreate.as_view(), name='flowchart-create'),
    path('flowcharts/import/', views.flowchart_import, name='flowchart-import'),
    path('flowcharts/<int:pk>/export/', views.flowchart_export, name='flowchart-export'),
    path('flowcharts/<int:pk>/', views.flowchart_detail, name='flowchart-detail'),
    path('flowcharts/<int:pk>/update/', views.FlowchartUpdate.as_view(), name='flowchart-update'),
    path('flowcharts/<int:pk>/delete/', views.FlowchartDelete.as_view(), name='flowchart-delete'),
    path('flowcharts/<int:pk>/archive/', views.flowchart_archive, name='flowchart-archive'),
    path('flowcharts/<int:pk>/auto-layout/', views.flowchart_auto_layout, name='flowchart-auto-layout'),
    path('flowcharts/<int:pk>/positions/', views.flowchart_batch_positions, name='flowchart-batch-positions'),
    path('flowcharts/<int:pk>/share/', views.flowchart_share, name='flowchart-share'),
    path('flowcharts/<int:pk>/share/<int:share_id>/remove/', views.flowchart_share_remove, name='flowchart-share-remove'),
    path('flowcharts/<int:pk>/invite/<int:invite_id>/remove/', views.flowchart_invite_remove, name='flowchart-invite-remove'),

    path('flowcharts/<int:flowchart_pk>/nodes/create/', views.node_create, name='node-create'),
    path('flowcharts/<int:flowchart_pk>/nodes/quick-add/', views.node_quick_add, name='node-quick-add'),
    path('nodes/<int:pk>/', views.NodeDetail.as_view(), name='node-detail'),
    path('nodes/<int:pk>/update/', views.NodeUpdate.as_view(), name='node-update'),
    path('nodes/<int:pk>/delete/', views.NodeDelete.as_view(), name='node-delete'),
    path('nodes/<int:pk>/quick-delete/', views.node_quick_delete, name='node-quick-delete'),
    path('nodes/<int:pk>/reparent/', views.node_reparent, name='node-reparent'),
    path('nodes/<int:pk>/tags/<int:tag_id>/add/', views.node_add_tag, name='node-add-tag'),
    path('nodes/<int:pk>/tags/<int:tag_id>/remove/', views.node_remove_tag, name='node-remove-tag'),

    path('tags/', views.TagList.as_view(), name='tag-index'),
    path('tags/create/', views.TagCreate.as_view(), name='tag-create'),
    path('tags/<int:pk>/', views.TagDetail.as_view(), name='tag-detail'),
    path('tags/<int:pk>/update/', views.TagUpdate.as_view(), name='tag-update'),
    path('tags/<int:pk>/delete/', views.TagDelete.as_view(), name='tag-delete'),

    # Documents (NDA / signable docs)
    path('documents/', views.document_list, name='document-index'),
    path('documents/create/', views.document_create, name='document-create'),
    path('documents/<int:pk>/', views.document_detail, name='document-detail'),
    path('documents/<int:pk>/edit/', views.document_edit, name='document-edit'),
    path('documents/<int:pk>/delete/', views.document_delete, name='document-delete'),
    path('documents/<int:pk>/download/', views.document_download, name='document-download'),
    path('sign/<uuid:token>/', views.document_public_sign, name='document-public-sign'),
    path('sign/<uuid:token>/download/', views.document_public_download, name='document-public-download'),
]
