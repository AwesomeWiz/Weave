import React from 'react';
import ReactDOM from 'react-dom/client';
import '@fontsource/inter/400.css';
import '@fontsource/inter/500.css';
import '@fontsource/inter/600.css';
import '@fontsource-variable/source-serif-4/standard.css';
import '@xyflow/react/dist/style.css';
import './styles/tokens.css';
import './styles/globals.css';
import './styles/product.css';
import App from './App';

ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><App /></React.StrictMode>);
