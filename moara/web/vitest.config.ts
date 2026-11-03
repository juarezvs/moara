import {defineConfig} from 'vitest/config';
export default defineConfig({
  cacheDir:'.cache/vitest',
  test:{fsModuleCachePath:'.cache/vitest-modules'}
});
