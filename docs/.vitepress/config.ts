import { defineConfig } from 'vitepress'

export default defineConfig({
  title: 'Droplegen',
  description: 'Fluigent Drop-Seq Microfluidics Control',
  themeConfig: {
    nav: [
      { text: 'Guide', link: '/guide/getting-started' },
      { text: 'Features', link: '/features/control-panel' },
      { text: 'Reference', link: '/reference/makefile' },
    ],
    sidebar: [
      {
        text: 'Guide',
        items: [
          { text: 'Getting Started', link: '/guide/getting-started' },
          { text: 'Architecture', link: '/guide/architecture' },
          { text: 'Configuration', link: '/guide/configuration' },
        ],
      },
      {
        text: 'Features',
        items: [
          { text: 'Control Panel', link: '/features/control-panel' },
          { text: 'Pipelines', link: '/features/pipelines' },
          { text: 'Monitoring', link: '/features/monitoring' },
          { text: 'Data Logging', link: '/features/data-logging' },
        ],
      },
      {
        text: 'Reference',
        items: [
          { text: 'Makefile Targets', link: '/reference/makefile' },
        ],
      },
    ],
    socialLinks: [
      { icon: 'github', link: 'https://github.com/alexeystroganov/droplegen' },
    ],
  },
})
