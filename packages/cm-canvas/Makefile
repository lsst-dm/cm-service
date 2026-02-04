NPM_LOCKFILE := package-lock.json
CM_STATIC_CONTENT_DIR ?= ../cm-web/src/lsst/cmservice/web/static

$(NPM_LOCKFILE):
	npm install

.PHONY: clean
clean:
	rm -f $(NPM_LOCKFILE)
	rm -rf dist/

.PHONY: dist
dist: $(NPM_LOCKFILE)
	npm run build
	cp dist/*.iife.js $(CM_STATIC_CONTENT_DIR)

rebuild: clean dist
