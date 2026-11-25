# Install script for directory: /home/serg/prometeus/update/padavan-4.4/trunk/libs/libgetdns/getdns-1.7.3

# Set the install prefix
if(NOT DEFINED CMAKE_INSTALL_PREFIX)
  set(CMAKE_INSTALL_PREFIX "/")
endif()
string(REGEX REPLACE "/$" "" CMAKE_INSTALL_PREFIX "${CMAKE_INSTALL_PREFIX}")

# Set the install configuration name.
if(NOT DEFINED CMAKE_INSTALL_CONFIG_NAME)
  if(BUILD_TYPE)
    string(REGEX REPLACE "^[^A-Za-z0-9_]+" ""
           CMAKE_INSTALL_CONFIG_NAME "${BUILD_TYPE}")
  else()
    set(CMAKE_INSTALL_CONFIG_NAME "Release")
  endif()
  message(STATUS "Install configuration: \"${CMAKE_INSTALL_CONFIG_NAME}\"")
endif()

# Set the component getting installed.
if(NOT CMAKE_INSTALL_COMPONENT)
  if(COMPONENT)
    message(STATUS "Install component: \"${COMPONENT}\"")
    set(CMAKE_INSTALL_COMPONENT "${COMPONENT}")
  else()
    set(CMAKE_INSTALL_COMPONENT)
  endif()
endif()

# Install shared libraries without execute permission?
if(NOT DEFINED CMAKE_INSTALL_SO_NO_EXE)
  set(CMAKE_INSTALL_SO_NO_EXE "1")
endif()

# Is this installation the result of a crosscompile?
if(NOT DEFINED CMAKE_CROSSCOMPILING)
  set(CMAKE_CROSSCOMPILING "TRUE")
endif()

# Set default install directory permissions.
if(NOT DEFINED CMAKE_OBJDUMP)
  set(CMAKE_OBJDUMP "/home/serg/prometeus/update/padavan-4.4/toolchain-mipsel/toolchain-4.4.x/bin/mipsel-linux-uclibc-objdump")
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "Unspecified" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/usr/lib" TYPE STATIC_LIBRARY FILES "/home/serg/prometeus/update/padavan-4.4/trunk/libs/libgetdns/getdns-1.7.3/build/libgetdns.a")
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "Unspecified" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/usr/lib" TYPE STATIC_LIBRARY FILES "/home/serg/prometeus/update/padavan-4.4/trunk/libs/libgetdns/getdns-1.7.3/build/libgetdns_ext_ev.a")
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "Unspecified" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/usr/include" TYPE DIRECTORY FILES "/home/serg/prometeus/update/padavan-4.4/trunk/libs/libgetdns/getdns-1.7.3/build/getdns")
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "Unspecified" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/usr/share/man" TYPE DIRECTORY FILES "/home/serg/prometeus/update/padavan-4.4/trunk/libs/libgetdns/getdns-1.7.3/build/man3")
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "Unspecified" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/usr/share/doc/getdns" TYPE FILE FILES
    "/home/serg/prometeus/update/padavan-4.4/trunk/libs/libgetdns/getdns-1.7.3/AUTHORS"
    "/home/serg/prometeus/update/padavan-4.4/trunk/libs/libgetdns/getdns-1.7.3/ChangeLog"
    "/home/serg/prometeus/update/padavan-4.4/trunk/libs/libgetdns/getdns-1.7.3/COPYING"
    "/home/serg/prometeus/update/padavan-4.4/trunk/libs/libgetdns/getdns-1.7.3/LICENSE"
    "/home/serg/prometeus/update/padavan-4.4/trunk/libs/libgetdns/getdns-1.7.3/NEWS"
    "/home/serg/prometeus/update/padavan-4.4/trunk/libs/libgetdns/getdns-1.7.3/README.md"
    )
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "Unspecified" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/usr/share/doc/getdns/spec" TYPE FILE FILES "/home/serg/prometeus/update/padavan-4.4/trunk/libs/libgetdns/getdns-1.7.3/spec/index.html")
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "Unspecified" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/usr/lib/pkgconfig" TYPE FILE FILES "/home/serg/prometeus/update/padavan-4.4/trunk/libs/libgetdns/getdns-1.7.3/build/getdns.pc")
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "Unspecified" OR NOT CMAKE_INSTALL_COMPONENT)
  message("***
***  !!! IMPORTANT !!!!
***
***  From release 1.2.0, getdns comes with built-in DNSSEC
***  trust anchor management.  External trust anchor management,
***  for example with unbound-anchor, is no longer necessary
***  and no longer recommended.
***
***  Previously installed trust anchors, in the default location -
***
***        /etc/unbound/getdns-root.key
***
***  - will be preferred and used for DNSSEC validation, however
***  getdns will fallback to trust-anchors obtained via built-in
***  trust anchor management when the anchors from the default
***  location fail to validate the root DNSKEY rrset.
***
***  To prevent expired DNSSEC trust anchors to be used for
***  validation, we strongly recommend removing the trust anchors
***  on the default location when there is no active external
***  trust anchor management keeping it up-to-date.
***")
endif()

if(CMAKE_INSTALL_COMPONENT)
  set(CMAKE_INSTALL_MANIFEST "install_manifest_${CMAKE_INSTALL_COMPONENT}.txt")
else()
  set(CMAKE_INSTALL_MANIFEST "install_manifest.txt")
endif()

string(REPLACE ";" "\n" CMAKE_INSTALL_MANIFEST_CONTENT
       "${CMAKE_INSTALL_MANIFEST_FILES}")
file(WRITE "/home/serg/prometeus/update/padavan-4.4/trunk/libs/libgetdns/getdns-1.7.3/build/${CMAKE_INSTALL_MANIFEST}"
     "${CMAKE_INSTALL_MANIFEST_CONTENT}")
