const rebase_error_message = `
This step failed because you merged the 'main' or release backport branch 'vX.Y.x' into the development branch, likely by clicking the 'Update branch' button on the GitHub pull request page.

In order to bring this pull request to a mergeable state, update the 'main' or backport branch locally and rebase against it.

See https://developer.lsst.io/work/flow.html#pushing-code for detailed instructions.

To avoid this error in the future, rebase against the latest 'main' or backport branch by following the instructions above, or use the little down arrow on the right side of 'Update branch' and click 'Update with rebase' option.
`.trim();

export default {
  defaultIgnores: false,
  ignores: [(commit) => !/^Merge branch/.test(commit)],
  plugins: [
    {
      rules: {
        "rebase-checker": (commitMessage, when, pattern) => {
          const { raw } = commitMessage;
          if (!pattern) return [false, "missing pattern"];
          const regex = new RegExp(pattern);
          let result = regex.test(raw ?? "");
          if (when === "never") result = !result;
          return [result, rebase_error_message];
        },
      },
    },
  ],
  rules: {
    "rebase-checker": [
      2,
      "never",
      /^Merge branch '?(main|master)'? into (.*?)(?:\r?\n)*$/,
    ],
  },
};
