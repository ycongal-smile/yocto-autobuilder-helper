/*
 * Copyright (C) 2020 Richard Purdie
 *
 * SPDX-License-Identifier: GPL-2.0-only
 *
 * Needs sudo setcap 'cap_sys_nice=ep' renice
 */

#include <sys/time.h>
#include <sys/resource.h>
#include <sys/syscall.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

enum {
    IOPRIO_WHO_PROCESS = 1,
};

#define IOPRIO_CLASS_SHIFT 13
#define IOPRIO_PRIO_MASK ((1UL << IOPRIO_CLASS_SHIFT) - 1)
#define IOPRIO_PRIO_CLASS(mask) ((mask) >> IOPRIO_CLASS_SHIFT)
#define IOPRIO_PRIO_DATA(mask) ((mask) & IOPRIO_PRIO_MASK)
#define IOPRIO_PRIO_VALUE(class, data) (((class) << IOPRIO_CLASS_SHIFT) | data)

int main(int argc, char *argv[])
{
    int pid, rc;
    if (argc != 2) {
        printf("Please specify only the process PID to adjust\n");
        exit(1);
    }
    pid = atoi(argv[1]);
    rc = setpriority(PRIO_PROCESS, pid, -5);
    if (rc != 0) {
        printf("setpriority failed: %d\n", rc);
        exit(1);
    }
    rc = syscall(__NR_ioprio_set, IOPRIO_WHO_PROCESS, pid, IOPRIO_PRIO_VALUE(2, 0));
    if (rc != 0) {
        printf("ioprio_set failed: %d\n", rc);
        exit(1);
    }
}
