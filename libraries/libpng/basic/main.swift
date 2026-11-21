// Otok examples (c) Alexander A Pototskiy
// SPDX-License-Identifier: 0BSD
//
// libpng from Swift: the module PNG of otok's package, the same round trip as main.c.

import Foundation
import PNG

let width: UInt32 = 16
let height: UInt32 = 8
var pixels = [UInt8](repeating: 0, count: Int(width * height) * 4)
for i in 0..<Int(width * height) {
    pixels[i * 4 + 0] = UInt8(truncatingIfNeeded: i * 3)
    pixels[i * 4 + 1] = UInt8(truncatingIfNeeded: 255 - i)
    pixels[i * 4 + 2] = UInt8(truncatingIfNeeded: i * 7)
    pixels[i * 4 + 3] = 255
}

// PNG_FORMAT_RGBA is a macro of two flags, which Swift does not import
let rgba = UInt32(PNG_FORMAT_FLAG_COLOR | PNG_FORMAT_FLAG_ALPHA)

func fail(_ what: String) -> Never {
    print(what)
    exit(1)
}

var image = png_image()
image.version = UInt32(PNG_IMAGE_VERSION)
image.width = width
image.height = height
image.format = rgba

// the size first, then the PNG itself
var size: png_alloc_size_t = 0
if png_image_write_to_memory(&image, nil, &size, 0, pixels, 0, nil) == 0 { fail("png_image_write_to_memory failed") }
var png = [UInt8](repeating: 0, count: Int(size))
if png_image_write_to_memory(&image, &png, &size, 0, pixels, 0, nil) == 0 { fail("png_image_write_to_memory failed") }

var read = png_image()
read.version = UInt32(PNG_IMAGE_VERSION)
if png_image_begin_read_from_memory(&read, png, Int(size)) == 0 { fail("png_image_begin_read_from_memory failed") }
read.format = rgba
var back = [UInt8](repeating: 0, count: pixels.count)
if read.width != width || read.height != height || png_image_finish_read(&read, nil, &back, 0, nil) == 0 {
    fail("png_image_finish_read failed")
}
if back != pixels { fail("the pixels came back changed") }

print("libpng \(String(cString: png_get_libpng_ver(nil))) from Swift: \(width)x\(height) in \(size) bytes")
print("ok")
