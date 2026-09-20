import js from '@eslint/js'
import globals from 'globals'
import react from 'eslint-plugin-react'
export default [
  { ignores: ['dist/**','node_modules/**'] },
  { files: ['src/**/*.{js,jsx}'], languageOptions: { globals: globals.browser, parserOptions: { ecmaFeatures: { jsx: true } } }, plugins: { react }, rules: { ...js.configs.recommended.rules, 'react/jsx-uses-vars':'error', 'react/jsx-uses-react':'off', 'no-unused-vars':['warn',{argsIgnorePattern:'^_'}] } }
]
