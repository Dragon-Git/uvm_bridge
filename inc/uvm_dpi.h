//----------------------------------------------------------------------
// Copyright 2010-2017 Mentor Graphics Corporation
// Copyright 2010 Synopsys, Inc.
// Copyright 2010-2018 Cadence Design Systems, Inc.
// Copyright 2013 NVIDIA Corporation
//   All Rights Reserved Worldwide
//
//   Licensed under the Apache License, Version 2.0 (the
//   "License"); you may not use this file except in
//   compliance with the License.  You may obtain a copy of
//   the License at
//
//       http://www.apache.org/licenses/LICENSE-2.0
//
//   Unless required by applicable law or agreed to in
//   writing, software distributed under the License is
//   distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
//   CONDITIONS OF ANY KIND, either express or implied.  See
//   the License for the specific language governing
//   permissions and limitations under the License.
//----------------------------------------------------------------------

//
// Top level header file that wraps all requirements which
// are common to the various C/C++ files in UVM.
//

#ifndef UVM_DPI__H
#define UVM_DPI__H

// On Windows, disable dllimport for VPI/DPI functions so that
// /FORCE:UNRESOLVED can handle them as regular undefined symbols.
#ifdef _WIN32
  #ifndef PLI_DLLISPEC
    #define PLI_DLLISPEC
  #endif
  #ifndef DPI_DLLISPEC
    #define DPI_DLLISPEC
  #endif
#endif

#include <stdlib.h>
#include "vpi_user.h"
#include "veriuser.h"
#include "svdpi.h"
#include <string.h>
#include <stdio.h>
#include <limits.h>

// POSIX regex.h is not available on Windows MSVC
// On Windows, we disable the regex functions (uvm_dpi_regcomp, uvm_dpi_regexec, uvm_dpi_regfree)
// as they are not commonly used in the core svuvm functionality
#ifdef _WIN32
  // Define regex_t as a placeholder type on Windows
  typedef struct {} regex_t;
  #define REG_EXTENDED 0
  #define REG_ICASE 0
  #define REG_NOSUB 0
  #define REG_NEWLINE 0
  #define REG_NOMATCH 1
#else
  #include <regex.h>
#endif

// The following consts and method call are for
// internal usage by the UVM DPI implementation,
// and are not intended for public use.
static const int M_UVM_INFO = 0;
static const int M_UVM_WARNING = 1;
static const int M_UVM_ERROR = 2;
static const int M_UVM_FATAL = 3;

static const int M_UVM_NONE = 0;
static const int M_UVM_LOW = 100;
static const int M_UVM_MEDIUM = 200;
static const int M_UVM_HIGH = 300;
static const int M_UVM_FULL = 400;
static const int M_UVM_DEBUG = 500;

void m_uvm_report_dpi(int severity,
                      char* id,
                      char* message,
                      int verbosity,
                      char* file,
                      int linenum);

int int_str_max( int );

int uvm_hdl_check_path(char *path);
int uvm_hdl_read(char *path, p_vpi_vecval value);
int uvm_hdl_deposit(char *path, p_vpi_vecval value);
int uvm_hdl_force(char *path, p_vpi_vecval value);
int uvm_hdl_release_and_read(char *path, p_vpi_vecval value);
int uvm_hdl_release(char *path);

void push_data(int lvl,char *entry, int cmd);
void walk_level(int lvl, int argc, char**argv,int cmd);
const char *uvm_dpi_get_next_arg_c (int init);
extern char* uvm_dpi_get_tool_name_c ();
extern char* uvm_dpi_get_tool_version_c ();
extern regex_t* uvm_dpi_regcomp (char* pattern);
extern int uvm_dpi_regexec (regex_t* re, char* str);
extern void uvm_dpi_regfree (regex_t* re);

#endif