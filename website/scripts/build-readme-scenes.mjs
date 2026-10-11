import {createRequire} from 'node:module';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import fs from 'node:fs/promises';
import {langPlugin} from './lang-plugin.mjs';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
let req=createRequire(path.join(root,'package.json'));
try {req.resolve('esbuild');} catch {req=createRequire(path.join(root,'../renderer/package.json'));}
const {build}=req('esbuild');
await build({entryPoints:[path.join(root,'product/readme.jsx')],outfile:path.join(root,'product-build/readme.js'),bundle:true,minify:true,format:'iife',jsx:'automatic',nodePaths:[req.resolve('react/package.json').replace(/react[\\/]package.json$/,'')],define:{'process.env.NODE_ENV':'"production"',__LANG__:'"zh"'},plugins:[langPlugin('zh')],target:['es2022'],loader:{'.woff2':'file'},assetNames:'fonts/[name]-[hash]'});
await fs.writeFile(path.join(root,'product-build/readme.html'),'<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>兔白字幕 · README 演示</title><link rel="stylesheet" href="readme.css"><div id="root"></div><script src="readme.js"></script></html>');
console.log('Fixed README scenes built. Main product entry unchanged.');
