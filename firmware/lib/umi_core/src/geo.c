#include "umi/core/geo.h"

#include <math.h>

#include "umi/protocol_gen.h"

#define DEG_TO_RAD (3.14159265358979323846 / 180.0)
#define E7_TO_RAD (DEG_TO_RAD / 1e7)

double umi_geo_distance_m(umi_geo_point_t a, umi_geo_point_t b)
{
    double lat1 = a.lat_e7 * E7_TO_RAD;
    double lat2 = b.lat_e7 * E7_TO_RAD;
    double dlat = lat2 - lat1;
    double dlon = ((double)b.lon_e7 - (double)a.lon_e7) * E7_TO_RAD;
    double s = sin(dlat / 2.0);
    double t = sin(dlon / 2.0);
    double h = s * s + cos(lat1) * cos(lat2) * t * t;
    return 2.0 * (double)UMI_GEO_EARTH_RADIUS_M * asin(sqrt(h < 1.0 ? h : 1.0));
}

double umi_geo_bearing_deg(umi_geo_point_t a, umi_geo_point_t b)
{
    double lat1 = a.lat_e7 * E7_TO_RAD;
    double lat2 = b.lat_e7 * E7_TO_RAD;
    double dlon = ((double)b.lon_e7 - (double)a.lon_e7) * E7_TO_RAD;
    double y = sin(dlon) * cos(lat2);
    double x = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(dlon);
    double deg = atan2(y, x) / DEG_TO_RAD;
    return deg < 0.0 ? deg + 360.0 : deg;
}

double umi_geo_heading_diff_deg(double a, double b)
{
    double d = fmod(b - a, 360.0);
    if (d <= -180.0) {
        d += 360.0;
    } else if (d > 180.0) {
        d -= 360.0;
    }
    return d;
}

bool umi_geo_maybe_within(umi_geo_point_t a, umi_geo_point_t b, double radius_m)
{
    const double m_per_e7 = (double)UMI_GEO_EARTH_RADIUS_M * E7_TO_RAD;
    /* 1 % slack covers the latitude change across the box. */
    double max_e7 = 1.01 * radius_m / m_per_e7;
    if (fabs((double)a.lat_e7 - (double)b.lat_e7) > max_e7) {
        return false;
    }
    double cos_lat = cos(a.lat_e7 * E7_TO_RAD);
    return fabs((double)a.lon_e7 - (double)b.lon_e7) * cos_lat <= max_e7;
}
