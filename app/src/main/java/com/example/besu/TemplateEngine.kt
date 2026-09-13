package com.example.besu

object TemplateEngine {
    private val variableRegex = Regex("""\{VAR(?::([A-C]))?\}""")
    private val computerRegex = Regex("""\[COMPUTER:([A-Z0-9_]+)\]""")

    fun countVariables(template: String): Int {
        return variableRegex.findAll(template).count()
    }

    fun getVariableTags(template: String): List<String?> {
        return variableRegex.findAll(template).map { match ->
            match.groups[1]?.value
        }.toList()
    }

    fun countComputerTags(template: String): Int {
        return computerRegex.findAll(template).count()
    }

    // One entry per occurrence (not deduplicated), in template order --
    // mirrors getVariableTags, since computerFallbacks below is positional
    // the same way {VAR} local values are.
    fun getComputerTags(template: String): List<String> {
        return computerRegex.findAll(template).map { match ->
            match.groupValues[1]
        }.toList()
    }

    fun resolve(
        template: String,
        localValues: List<String>,
        overrides: Map<String, RootOverrideValue> = emptyMap(),
        computerFallbacks: List<String> = emptyList(),
        computerActiveValues: Map<String, String> = emptyMap()
    ): String {
        var variableIndex = 0

        val afterVariables = variableRegex.replace(template) { match ->
            val tag = match.groups[1]?.value
            val localValue = localValues.getOrNull(variableIndex).orEmpty()

            variableIndex++

            val rootOverride = tag?.let { overrideTag ->
                overrides[overrideTag]
            }

            if (
                rootOverride?.enabled == true &&
                rootOverride.value.isNotBlank()
            ) {
                rootOverride.value
            } else {
                localValue
            }
        }

        var computerIndex = 0

        return computerRegex.replace(afterVariables) { match ->
            val categoryId = match.groupValues[1]
            val fallback = computerFallbacks.getOrNull(computerIndex).orEmpty()

            computerIndex++

            val activeValue = computerActiveValues[categoryId].orEmpty()
            activeValue.ifBlank { fallback }
        }
    }
}