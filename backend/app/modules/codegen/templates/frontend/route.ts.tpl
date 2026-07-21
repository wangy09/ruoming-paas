{
  path: '{{ route_path }}',
  name: '{{ entity_name }}',
  component: () => import('@/views/{{ module_name }}/index.vue'),
  meta: { title: '{{ page_title }}', icon: 'Grid', affix: false },
},