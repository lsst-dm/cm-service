NPM_LOCKFILE := package-lock.json

$(NPM_LOCKFILE):
	npm install

.PHONY: clean
clean:
	rm -f $(NPM_LOCKFILE)
	rm -rf dist/

dist: $(NPM_LOCKFILE)
	npm run build

rebuild: clean dist
