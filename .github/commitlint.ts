// A permissive/warning-only ruleset based on "@commitlint/config-conventional"

import { RuleConfigCondition, RuleConfigSeverity, TargetCaseType } from "@commitlint/types";

export default {
	parserPreset: "conventional-changelog-conventionalcommits",
	rules: {
		"body-leading-blank": [RuleConfigSeverity.Warning, "always"] as const,
		"body-max-line-length": [RuleConfigSeverity.Warning, "always", 100] as const,
		"footer-leading-blank": [RuleConfigSeverity.Warning, "always"] as const,
		"footer-max-line-length": [RuleConfigSeverity.Warning, "always", 100] as const,
		"header-max-length": [RuleConfigSeverity.Warning, "always", 100] as const,
		"header-trim": [RuleConfigSeverity.Warning, "always"] as const,
		"subject-case": [
			RuleConfigSeverity.Warning,
			"never",
			["sentence-case", "start-case", "pascal-case", "upper-case"],
		] as [RuleConfigSeverity, RuleConfigCondition, TargetCaseType[]],
		"subject-empty": [RuleConfigSeverity.Warning, "never"] as const,
		"subject-full-stop": [RuleConfigSeverity.Warning, "never", "."] as const,
		"type-case": [RuleConfigSeverity.Warning, "always", "lower-case"] as const,
		"type-empty": [RuleConfigSeverity.Warning, "never"] as const,
		"type-enum": [
			RuleConfigSeverity.Warning,
			"always",
			[
				"build",
				"chore",
				"ci",
				"docs",
				"feat",
				"fix",
				"perf",
				"refactor",
				"revert",
				"style",
				"test",
			],
		] as [RuleConfigSeverity, RuleConfigCondition, string[]],
	},
};
