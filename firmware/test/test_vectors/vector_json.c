#include "vector_json.h"

#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <unity.h>

static const char *skip_space(const char *p)
{
    while (*p == ' ' || *p == '\t' || *p == '\r' || *p == '\n') {
        p++;
    }
    return p;
}

const char *vj_find(const char *json, const char *key)
{
    char quoted[VJ_MAX_KEY + 2];
    snprintf(quoted, sizeof quoted, "\"%s\"", key);
    /* A key is a quoted name followed by a colon; the same name as a string
     * value ("type": "end") is followed by a comma or a brace instead. */
    for (const char *p = strstr(json, quoted); p != NULL; p = strstr(p + 1, quoted)) {
        const char *after = skip_space(p + strlen(quoted));
        if (*after == ':') {
            return skip_space(after + 1);
        }
    }
    return NULL;
}

/* Copies one value into out; returns the position after it, NULL if too long. */
static const char *read_value(const char *p, char out[VJ_MAX_VALUE])
{
    size_t n = 0;
    if (*p == '"') {
        for (p++; *p != '"'; p++) {
            if (*p == '\0' || n + 1 >= VJ_MAX_VALUE) {
                return NULL;
            }
            out[n++] = *p;
        }
        p++;
    } else {
        bool array = *p == '[';
        for (; *p != '\0'; p++) {
            if (!array && (*p == ',' || *p == '}' || *p == ' ' || *p == '\n')) {
                break;
            }
            if (*p == ' ' || *p == '\n') {
                continue;
            }
            if (n + 1 >= VJ_MAX_VALUE) {
                return NULL;
            }
            out[n++] = *p;
            if (array && *p == ']') {
                p++;
                break;
            }
        }
    }
    out[n] = '\0';
    return p;
}

const char *vj_object(const char *p, vj_object_t *out)
{
    out->count = 0;
    p = skip_space(p);
    if (*p != '{') {
        return NULL;
    }
    p = skip_space(p + 1);
    while (*p != '}') {
        if (*p != '"' || out->count == VJ_MAX_FIELDS) {
            return NULL;
        }
        vj_field_t *field = &out->fields[out->count++];
        const char *end = strchr(p + 1, '"');
        size_t key_len = end == NULL ? 0 : (size_t)(end - (p + 1));
        if (key_len == 0 || key_len >= VJ_MAX_KEY) {
            return NULL;
        }
        memcpy(field->key, p + 1, key_len);
        field->key[key_len] = '\0';
        p = skip_space(end + 1);
        if (*p != ':') {
            return NULL;
        }
        p = read_value(skip_space(p + 1), field->value);
        if (p == NULL) {
            return NULL;
        }
        p = skip_space(p);
        if (*p == ',') {
            p = skip_space(p + 1);
        }
    }
    return p + 1;
}

bool vj_next_object(const char **p, vj_object_t *out)
{
    const char *at = *p;
    while (*at == '[' || *at == ',' || *at == ' ' || *at == '\t' || *at == '\r' || *at == '\n') {
        at++;
    }
    if (*at != '{') {
        return false;
    }
    at = vj_object(at, out);
    if (at == NULL) {
        return false;
    }
    *p = at;
    return true;
}

const char *vj_get(const vj_object_t *obj, const char *key)
{
    for (size_t i = 0; i < obj->count; i++) {
        if (strcmp(obj->fields[i].key, key) == 0) {
            return obj->fields[i].value;
        }
    }
    return NULL;
}

void vj_set(vj_object_t *obj, const char *key, const char *fmt, ...)
{
    TEST_ASSERT_LESS_THAN_size_t(VJ_MAX_FIELDS, obj->count);
    vj_field_t *field = &obj->fields[obj->count++];
    snprintf(field->key, sizeof field->key, "%s", key);
    va_list args;
    va_start(args, fmt);
    vsnprintf(field->value, sizeof field->value, fmt, args);
    va_end(args);
}
