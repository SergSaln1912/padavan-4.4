file(REMOVE_RECURSE
  "libgetdns.a"
  "libgetdns.pdb"
)

# Per-language clean rules from dependency scanning.
foreach(lang C)
  include(CMakeFiles/getdns.dir/cmake_clean_${lang}.cmake OPTIONAL)
endforeach()
