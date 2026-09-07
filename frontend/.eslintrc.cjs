module.exports = {
  env: { browser: true, es2020: true },
  extends: [
    'eslint:recommended',
    'prettier'
  ],
  parserOptions: { ecmaVersion: 'latest', sourceType: 'module' },
  rules: {
    'react/react-in-jsx-scope': 'off'
  }
}
