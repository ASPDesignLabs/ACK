cmake_minimum_required(VERSION 3.22.1)

project("cyber_audio")

add_library(
        cyber_audio
        SHARED
        cyber_audio.cpp
)

find_library(
        log-lib
        log
)

target_link_libraries(
        cyber_audio
        ${log-lib}
)
