/* Geodesy on the spherical Earth of protocol/constants.toml [geo], so distances
 * match the privacy trim and the backend. Coordinates are degrees x 1e7. */
#ifndef UMI_CORE_GEO_H
#define UMI_CORE_GEO_H

#include <stdbool.h>
#include <stdint.h>

typedef struct {
    int32_t lat_e7;
    int32_t lon_e7;
} umi_geo_point_t;

/* Great-circle distance in metres (haversine). */
double umi_geo_distance_m(umi_geo_point_t a, umi_geo_point_t b);

/* Initial bearing from a to b, degrees clockwise from north in [0, 360). */
double umi_geo_bearing_deg(umi_geo_point_t a, umi_geo_point_t b);

/* Signed smallest difference b - a between two headings, in (-180, 180]. */
double umi_geo_heading_diff_deg(double a, double b);

/* Cheap bounding-box pre-filter: false when the points are certainly farther
 * apart than radius_m, so the haversine only runs for nearby points. */
bool umi_geo_maybe_within(umi_geo_point_t a, umi_geo_point_t b, double radius_m);

#endif /* UMI_CORE_GEO_H */
