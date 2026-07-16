import * as esbuild from 'esbuild';

const watch = process.argv.includes('--watch');

const config = {
  entryPoints: ['src/main.ts'],
  bundle: true,
  outfile: 'dist/dashboard.js',
  format: 'iife',
  globalName: 'Dashboard',
  sourcemap: true,
  minify: false,
  target: 'es2022',
};

if (watch) {
  const ctx = await esbuild.context(config);
  await ctx.watch();
  console.log('watching for changes...');
} else {
  await esbuild.build(config);
  console.log('built dist/dashboard.js');
}
