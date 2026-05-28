BUN_LOCKFILE := bun.lock
NPM_LOCKFILE := package-lock.json
CM_STATIC_CONTENT_DIR ?= ../cm-web/src/lsst/cmservice/web/static

$(NPM_LOCKFILE):
	npm install

$(BUN_LOCKFILE):
	bun install

.PHONY: clean
clean:
	rm -f $(NPM_LOCKFILE)
	rm -f $(BUN_LOCKFILE)
	rm -rf dist/

.PHONY: dist
dist: $(BUN_LOCKFILE)
	bun run build
	cp dist/*.iife.js $(CM_STATIC_CONTENT_DIR)

rebuild: clean dist
