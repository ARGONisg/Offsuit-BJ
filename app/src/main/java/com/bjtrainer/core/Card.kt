package com.bjtrainer.core

enum class Card(val rank: String, val value: Int) {
    TWO("2", 2), THREE("3", 3), FOUR("4", 4), FIVE("5", 5), SIX("6", 6),
    SEVEN("7", 7), EIGHT("8", 8), NINE("9", 9), TEN("10", 10), ACE("A", 11);

    companion object {
        fun fromString(rankStr: String): Card? {
            val upper = rankStr.uppercase().trim()
            return entries.find { it.rank == upper || it.name == upper }
                ?: when(upper) {
                    "J", "Q", "K" -> TEN
                    "11" -> ACE
                    else -> null
                }
        }
    }
}
