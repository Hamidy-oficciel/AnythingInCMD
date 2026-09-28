#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdint.h>
#include <string.h>

typedef struct {
    char *data;
    Py_ssize_t length;
    Py_ssize_t capacity;
} OutputBuffer;

static int reserve_output(OutputBuffer *output, Py_ssize_t additional) {
    if (additional > PY_SSIZE_T_MAX - output->length) {
        PyErr_NoMemory();
        return -1;
    }
    Py_ssize_t required = output->length + additional;
    if (required <= output->capacity) {
        return 0;
    }
    Py_ssize_t capacity = output->capacity ? output->capacity : 4096;
    while (capacity < required) {
        if (capacity > PY_SSIZE_T_MAX / 2) {
            capacity = required;
            break;
        }
        capacity *= 2;
    }
    char *resized = PyMem_Realloc(output->data, (size_t)capacity);
    if (resized == NULL) {
        PyErr_NoMemory();
        return -1;
    }
    output->data = resized;
    output->capacity = capacity;
    return 0;
}

static int append_bytes(OutputBuffer *output, const char *text, Py_ssize_t size) {
    if (reserve_output(output, size) < 0) {
        return -1;
    }
    memcpy(output->data + output->length, text, (size_t)size);
    output->length += size;
    return 0;
}

static int append_char(OutputBuffer *output, char value) {
    if (reserve_output(output, 1) < 0) {
        return -1;
    }
    output->data[output->length++] = value;
    return 0;
}

static int append_number(OutputBuffer *output, unsigned int value) {
    char digits[3];
    Py_ssize_t count = 0;
    do {
        digits[count++] = (char)('0' + value % 10);
        value /= 10;
    } while (value != 0);
    while (count > 0) {
        if (append_char(output, digits[--count]) < 0) {
            return -1;
        }
    }
    return 0;
}

static unsigned int pixel_luminance(const unsigned char *pixel) {
    return (299U * pixel[0] + 587U * pixel[1] + 114U * pixel[2]) / 1000U;
}

static int append_color(OutputBuffer *output, const char *prefix,
                        unsigned int red, unsigned int green, unsigned int blue) {
    if (append_bytes(output, prefix, 7) < 0 ||
        append_number(output, red) < 0 || append_char(output, ';') < 0 ||
        append_number(output, green) < 0 || append_char(output, ';') < 0 ||
        append_number(output, blue) < 0 || append_char(output, 'm') < 0) {
        return -1;
    }
    return 0;
}

static PyObject *render_half_block(PyObject *self, PyObject *args) {
    Py_buffer frame;
    Py_ssize_t width;
    Py_ssize_t height;
    int color = 0;
    if (!PyArg_ParseTuple(args, "y*nn|p", &frame, &width, &height, &color)) {
        return NULL;
    }
    if (width < 1 || height < 1 || width > PY_SSIZE_T_MAX / 3 / height) {
        PyBuffer_Release(&frame);
        PyErr_SetString(PyExc_ValueError, "Frame dimensions must be positive and representable");
        return NULL;
    }
    if (frame.len != width * height * 3) {
        PyBuffer_Release(&frame);
        PyErr_SetString(PyExc_ValueError, "RGB frame byte count does not match its dimensions");
        return NULL;
    }

    OutputBuffer output = {NULL, 0, 0};
    const unsigned char *pixels = (const unsigned char *)frame.buf;
    const char *foreground = "\x1b[38;2;";
    const char *background = "\x1b[48;2;";
    const char reset[] = "\x1b[0m";
    const char block[] = "\xe2\x96\x80";
    Py_ssize_t rows = (height + 1) / 2;

    for (Py_ssize_t y = 0; y < height; y += 2) {
        for (Py_ssize_t x = 0; x < width; x++) {
            Py_ssize_t top_offset = (y * width + x) * 3;
            const unsigned char *top = pixels + top_offset;
            const unsigned char *bottom = y + 1 < height
                ? pixels + top_offset + width * 3
                : NULL;
            unsigned int top_red = color ? top[0] : pixel_luminance(top);
            unsigned int top_green = color ? top[1] : top_red;
            unsigned int top_blue = color ? top[2] : top_red;
            unsigned int bottom_red = bottom == NULL ? 0
                : color ? bottom[0] : pixel_luminance(bottom);
            unsigned int bottom_green = bottom == NULL ? 0
                : color ? bottom[1] : bottom_red;
            unsigned int bottom_blue = bottom == NULL ? 0
                : color ? bottom[2] : bottom_red;

            if (append_color(&output, foreground, top_red, top_green, top_blue) < 0 ||
                append_color(&output, background, bottom_red, bottom_green, bottom_blue) < 0 ||
                append_bytes(&output, block, 3) < 0) {
                goto error;
            }
        }
        if (append_bytes(&output, reset, 4) < 0) {
            goto error;
        }
        if (y + 2 < height && append_char(&output, '\n') < 0) {
            goto error;
        }
    }

    PyBuffer_Release(&frame);
    {
        PyObject *result = PyUnicode_DecodeUTF8(output.data, output.length, "strict");
        PyMem_Free(output.data);
        return result;
    }

error:
    PyBuffer_Release(&frame);
    PyMem_Free(output.data);
    return NULL;
}

static PyObject *render_ascii(PyObject *self, PyObject *args) {
    Py_buffer frame;
    Py_ssize_t width;
    Py_ssize_t height;
    if (!PyArg_ParseTuple(args, "y*nn", &frame, &width, &height)) {
        return NULL;
    }
    if (width < 1 || height < 1 || width > PY_SSIZE_T_MAX / 3 / height) {
        PyBuffer_Release(&frame);
        PyErr_SetString(PyExc_ValueError, "Frame dimensions must be positive and representable");
        return NULL;
    }
    if (frame.len != width * height * 3) {
        PyBuffer_Release(&frame);
        PyErr_SetString(PyExc_ValueError, "RGB frame byte count does not match its dimensions");
        return NULL;
    }

    OutputBuffer output = {NULL, 0, 0};
    const unsigned char *pixels = (const unsigned char *)frame.buf;
    const char ramp[] = "@%#*+=-:. ";
    for (Py_ssize_t y = 0; y < height; y++) {
        for (Py_ssize_t x = 0; x < width; x++) {
            const unsigned char *pixel = pixels + (y * width + x) * 3;
            unsigned int index = pixel_luminance(pixel) * 9U / 255U;
            if (append_char(&output, ramp[index]) < 0) {
                goto ascii_error;
            }
        }
        if (y + 1 < height && append_char(&output, '\n') < 0) {
            goto ascii_error;
        }
    }

    PyBuffer_Release(&frame);
    {
        PyObject *result = PyUnicode_DecodeASCII(output.data, output.length, "strict");
        PyMem_Free(output.data);
        return result;
    }

ascii_error:
    PyBuffer_Release(&frame);
    PyMem_Free(output.data);
    return NULL;
}

static PyMethodDef methods[] = {
    {"render_half_block", render_half_block, METH_VARARGS,
     "Render an RGB frame as terminal half-block cells."},
    {"render_ascii", render_ascii, METH_VARARGS,
     "Render an RGB frame as ASCII brightness characters."},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef module = {
    PyModuleDef_HEAD_INIT,
    "_native_renderer",
    NULL,
    -1,
    methods
};

PyMODINIT_FUNC PyInit__native_renderer(void) {
    return PyModule_Create(&module);
}