/* Reader for the canonical JSON of the golden vectors (protocol/vectors/README.md,
 * "Canonical JSON"): just enough to compare a C decoding with the reference's.
 * Objects there are flat (the header's fw_version array aside), keys are unique
 * and strings hold names and hex digits only, so neither nesting nor escapes
 * need handling. */
#ifndef UMI_TEST_VECTOR_JSON_H
#define UMI_TEST_VECTOR_JSON_H

#include <stdbool.h>
#include <stddef.h>

#define VJ_MAX_FIELDS 16
#define VJ_MAX_KEY 24
#define VJ_MAX_VALUE 520 /* the hex of a 255-byte payload, and its terminator */

typedef struct {
    char key[VJ_MAX_KEY];
    /* Strings without their quotes, arrays without spaces, other values as written. */
    char value[VJ_MAX_VALUE];
} vj_field_t;

typedef struct {
    vj_field_t fields[VJ_MAX_FIELDS];
    size_t count;
} vj_object_t;

/* Start of the value of `key` (first character after the colon); NULL if absent. */
const char *vj_find(const char *json, const char *key);

/* Parses the flat object at p ('{'); returns the position after '}', or NULL
 * if it is not one. */
const char *vj_object(const char *p, vj_object_t *out);

/* Steps through an array of objects: *p starts at '[' and each call parses the
 * next object into out. False at the closing ']' or on malformed input. */
bool vj_next_object(const char **p, vj_object_t *out);

/* Value of `key` in obj, NULL if absent. */
const char *vj_get(const vj_object_t *obj, const char *key);

/* Appends a field whose value is formatted like printf. */
void vj_set(vj_object_t *obj, const char *key, const char *fmt, ...)
    __attribute__((format(printf, 3, 4)));

#endif /* UMI_TEST_VECTOR_JSON_H */
