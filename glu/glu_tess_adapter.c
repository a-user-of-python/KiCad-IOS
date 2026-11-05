/*
 * glu_tess_adapter.c — the GLU tessellator subset, implemented over
 * libtess2. Part of the KiCad-IOS spike (GPLv3, matching upstream
 * KiCad); libtess2 itself is zlib-licensed (see deps stage).
 *
 * Semantics, matched to what KiCad's OpenGL GAL actually uses:
 *
 *  - Polygons arrive as ONE contour of GLdouble[3] vertices between
 *    gluTessBeginPolygon / gluTessEndPolygon (the adapter buffers any
 *    number of contours, like real GLU).
 *  - At gluTessEndPolygon the buffered contours are tessellated with
 *    libtess2 (TESS_POLYGONS, 3 vertices per element) and every output
 *    vertex is replayed, in triangle order, through the registered
 *    GLU_TESS_VERTEX_DATA callback (or GLU_TESS_VERTEX) together with
 *    the polygon data pointer from gluTessBeginPolygon. That is the
 *    same vertex stream real GLU produces once an EDGE_FLAG callback
 *    is registered (GLU then emits triangles only), which is exactly
 *    how KiCad configures it.
 *  - Self-intersections: real GLU reports them through COMBINE_DATA so
 *    the client can mint new vertices. libtess2's sweep computes the
 *    intersection vertices internally instead, so COMBINE_DATA is
 *    accepted but never invoked; the resulting geometry is the same.
 *  - Per-vertex data pointers: KiCad passes the vertex coordinates as
 *    the data pointer (gluTessVertex(tess, point, point)), and
 *    libtess2's unified output pool preserves coordinates, so the
 *    callback receives an equivalent GLdouble[3]. A client passing
 *    distinct per-vertex payloads would need them carried separately;
 *    KiCad does not.
 *  - TESSreal is double in this build (deps stage), so coordinates
 *    keep GLdouble precision end to end.
 */

#include "glu.h"

#include <stdlib.h>
#include <string.h>

#include <tesselator.h>


typedef void ( CALLBACK* TessCallbackFn )();

struct GLUtesselator
{
    GLenum        windingRule;      /* GLU_TESS_WINDING_* */
    TessCallbackFn vertexCb;        /* GLU_TESS_VERTEX */
    TessCallbackFn vertexDataCb;    /* GLU_TESS_VERTEX_DATA */
    TessCallbackFn combineDataCb;   /* GLU_TESS_COMBINE_DATA (never invoked, see above) */
    TessCallbackFn edgeFlagCb;      /* GLU_TESS_EDGE_FLAG */
    TessCallbackFn errorCb;         /* GLU_TESS_ERROR */

    void*         polygonData;
    TESStesselator* tess;

    /* Current contour being buffered (libtess2 wants whole contours). */
    GLdouble*     contour;
    size_t        contourCount;
    size_t        contourCapacity;
    int           inContour;
    int           inPolygon;
};


GLUtesselator* gluNewTess( void )
{
    GLUtesselator* tess = (GLUtesselator*) calloc( 1, sizeof( GLUtesselator ) );

    if( tess )
        tess->windingRule = GLU_TESS_WINDING_ODD;

    return tess;
}


void gluDeleteTess( GLUtesselator* aTess )
{
    if( !aTess )
        return;

    if( aTess->tess )
        tessDeleteTess( aTess->tess );

    free( aTess->contour );
    free( aTess );
}


void gluTessCallback( GLUtesselator* aTess, GLenum aWhich, void ( CALLBACK* aFn )() )
{
    if( !aTess )
        return;

    switch( aWhich )
    {
    case GLU_TESS_VERTEX:       aTess->vertexCb = (TessCallbackFn) aFn;      break;
    case GLU_TESS_VERTEX_DATA:  aTess->vertexDataCb = (TessCallbackFn) aFn;  break;
    case GLU_TESS_COMBINE_DATA: aTess->combineDataCb = (TessCallbackFn) aFn; break;
    case GLU_TESS_EDGE_FLAG:    aTess->edgeFlagCb = (TessCallbackFn) aFn;    break;
    case GLU_TESS_ERROR:        aTess->errorCb = (TessCallbackFn) aFn;       break;
    default: break; /* BEGIN/END callbacks: not used by KiCad; output is vertex stream only */
    }
}


void gluTessProperty( GLUtesselator* aTess, GLenum aWhich, GLdouble aValue )
{
    if( !aTess )
        return;

    if( aWhich == GLU_TESS_WINDING_RULE )
        aTess->windingRule = (GLenum) aValue;
    /* BOUNDARY_ONLY / TOLERANCE: accepted, not applicable to the replay model */
}


void gluTessNormal( GLUtesselator* aTess, GLdouble aX, GLdouble aY, GLdouble aZ )
{
    (void) aTess; (void) aX; (void) aY; (void) aZ;
}


void gluTessBeginPolygon( GLUtesselator* aTess, void* aData )
{
    if( !aTess )
        return;

    aTess->polygonData = aData;
    aTess->inPolygon = 1;

    if( aTess->tess )
        tessDeleteTess( aTess->tess );

    aTess->tess = tessNewTess( NULL );
}


void gluTessBeginContour( GLUtesselator* aTess )
{
    if( !aTess )
        return;

    aTess->contourCount = 0;
    aTess->inContour = 1;
}


void gluTessVertex( GLUtesselator* aTess, GLdouble* aLocation, void* aData )
{
    (void) aData; /* == aLocation in KiCad's use; see header note */

    if( !aTess || !aTess->inContour || !aLocation )
        return;

    if( aTess->contourCount == aTess->contourCapacity )
    {
        size_t    newCapacity = aTess->contourCapacity ? aTess->contourCapacity * 2 : 64;
        GLdouble* newBuffer = (GLdouble*) realloc( aTess->contour,
                                                   newCapacity * 3 * sizeof( GLdouble ) );

        if( !newBuffer )
            return;

        aTess->contour = newBuffer;
        aTess->contourCapacity = newCapacity;
    }

    memcpy( aTess->contour + aTess->contourCount * 3, aLocation, 3 * sizeof( GLdouble ) );
    aTess->contourCount++;
}


void gluTessEndContour( GLUtesselator* aTess )
{
    if( !aTess || !aTess->inContour )
        return;

    aTess->inContour = 0;

    if( aTess->tess && aTess->contourCount > 0 )
    {
        tessAddContour( aTess->tess, 3, aTess->contour,
                        (int) ( 3 * sizeof( GLdouble ) ), (int) aTess->contourCount );
    }

    aTess->contourCount = 0;
}


static int windingToTess2( GLenum aRule )
{
    switch( aRule )
    {
    case GLU_TESS_WINDING_NONZERO:     return TESS_WINDING_NONZERO;
    case GLU_TESS_WINDING_POSITIVE:    return TESS_WINDING_POSITIVE;
    case GLU_TESS_WINDING_NEGATIVE:    return TESS_WINDING_NEGATIVE;
    case GLU_TESS_WINDING_ABS_GEQ_TWO: return TESS_WINDING_ABS_GEQ_TWO;
    case GLU_TESS_WINDING_ODD:
    default:                           return TESS_WINDING_ODD;
    }
}


void gluTessEndPolygon( GLUtesselator* aTess )
{
    if( !aTess || !aTess->inPolygon )
        return;

    aTess->inPolygon = 0;

    if( !aTess->tess )
        return;

    if( !tessTesselate( aTess->tess, windingToTess2( aTess->windingRule ),
                         TESS_POLYGONS, 3, 3, NULL ) )
    {
        if( aTess->errorCb )
            ((void ( CALLBACK* )( GLenum )) aTess->errorCb)( GLU_TESS_MISSING_END_POLYGON );

        tessDeleteTess( aTess->tess );
        aTess->tess = NULL;
        return;
    }

    const TESSreal*  verts = tessGetVertices( aTess->tess );
    const TESSindex* elems = tessGetElements( aTess->tess );
    const int        elemCount = tessGetElementCount( aTess->tess );

    for( int i = 0; i < elemCount; i++ )
    {
        if( aTess->edgeFlagCb )
            ((void ( CALLBACK* )( GLboolean )) aTess->edgeFlagCb)( 1 );

        for( int j = 0; j < 3; j++ )
        {
            TESSindex idx = elems[i * 3 + j];

            if( idx == TESS_UNDEF || !verts )
                continue;

            /* TESSreal is double in this build: the pool vertex is a
             * GLdouble[3], matching what KiCad's callback expects. */
            GLdouble* vertex = (GLdouble*) ( verts + (size_t) idx * 3 );

            if( aTess->vertexDataCb )
                ((void ( CALLBACK* )( void*, void* )) aTess->vertexDataCb)(
                        (void*) vertex, aTess->polygonData );
            else if( aTess->vertexCb )
                ((void ( CALLBACK* )( void* )) aTess->vertexCb)( (void*) vertex );
        }
    }

    tessDeleteTess( aTess->tess );
    aTess->tess = NULL;
}


const unsigned char* gluErrorString( GLenum aError )
{
    switch( aError )
    {
    case GLU_TESS_MISSING_BEGIN_POLYGON: return (const unsigned char*) "missing gluTessBeginPolygon";
    case GLU_TESS_MISSING_BEGIN_CONTOUR: return (const unsigned char*) "missing gluTessBeginContour";
    case GLU_TESS_MISSING_END_POLYGON:   return (const unsigned char*) "missing gluTessEndPolygon";
    case GLU_TESS_MISSING_END_CONTOUR:   return (const unsigned char*) "missing gluTessEndContour";
    case GLU_TESS_COORD_TOO_LARGE:       return (const unsigned char*) "coordinate out of range";
    case GLU_TESS_NEED_COMBINE_CALLBACK: return (const unsigned char*) "need combine callback";
    default:                             return (const unsigned char*) "unknown tessellation error";
    }
}
