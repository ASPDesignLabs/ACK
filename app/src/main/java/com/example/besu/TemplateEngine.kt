package com.example.besu

object TemplateEngine {
    private val variableRegex = Regex("""\{VAR(?::([A-C]))?\}""")

    fun countVariables(template: String): Int {
        return variableRegex.findAll(template).count()
    }

    fun getVariableTags(template: String): List<String?> {
        return variableRegex.findAll(template).map { match ->
            match.groups[1]?.value
        }.toList()
    }

    fun resolve(
        template: String,
        localValues: List<String>,
        overrides: Map<String, RootOverrideValue> = emptyMap()
    ): String {
        var variableIndex = 0

        return variableRegex.replace(template) { match ->
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
    }
}