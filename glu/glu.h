/*
 * glu.h — GLU tessellator API subset for the KiCad iOS port.
 *
 * Part of the KiCad-IOS spike (GPLv3, matching upstream KiCad).
 *
 * iOS has no GLU. KiCad's OpenGL GAL (common/gal/opengl/opengl_gal.cpp)
 * uses exactly one part of GLU: the polygon tessellator (gluNewTess and
 * friends), driven through VERTEX_DATA / COMBINE_DATA / EDGE_FLAG /
 * ERROR callbacks. This header declares that subset; the implementation
 * in glu_tess_adapter.c maps it onto libtess2 (zlib licence), whose
 * sweep-line tessellator implements the same winding-rule model.
 *
 * Only the declarations KiCad's code names are provided.
 */

#ifndef KICAD_IOS_GLU_H
#define KICAD_IOS_GLU_H

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/* GL base types (identical typedefs to OpenGLES ES3 gl.h, so the two
 * headers can coexist in either order). */
typedef unsigned int   GLenum;
typedef unsigned char  GLboolean;
typedef double         GLdouble;
typedef void           GLvoid;

#ifndef CALLBACK
#define CALLBACK
#endif

typedef struct GLUtesselator GLUtesselator;

/* Tessellation callback types */
#define GLU_TESS_BEGIN           100100
#define GLU_TESS_VERTEX          100101
#define GLU_TESS_END             100102
#define GLU_TESS_ERROR           100103
#define GLU_TESS_EDGE_FLAG       100104
#define GLU_TESS_COMBINE         100105
#define GLU_TESS_BEGIN_DATA      100106
#define GLU_TESS_VERTEX_DATA     100107
#define GLU_TESS_END_DATA        100108
#define GLU_TESS_ERROR_DATA      100109
#define GLU_TESS_EDGE_FLAG_DATA  100110
#define GLU_TESS_COMBINE_DATA    100111

/* Tessellation properties */
#define GLU_TESS_WINDING_RULE    100140
#define GLU_TESS_BOUNDARY_ONLY   100141
#define GLU_TESS_TOLERANCE       100142

/* Winding rules */
#define GLU_TESS_WINDING_ODD          100130
#define GLU_TESS_WINDING_NONZERO      100131
#define GLU_TESS_WINDING_POSITIVE     100132
#define GLU_TESS_WINDING_NEGATIVE     100133
#define GLU_TESS_WINDING_ABS_GEQ_TWO  100134

/* Tessellation errors */
#define GLU_TESS_MISSING_BEGIN_POLYGON  100151
#define GLU_TESS_MISSING_BEGIN_CONTOUR  100152
#define GLU_TESS_MISSING_END_POLYGON    100153
#define GLU_TESS_MISSING_END_CONTOUR    100154
#define GLU_TESS_COORD_TOO_LARGE        100155
#define GLU_TESS_NEED_COMBINE_CALLBACK  100156

GLUtesselator* gluNewTess( void );
void           gluDeleteTess( GLUtesselator* aTess );
void           gluTessCallback( GLUtesselator* aTess, GLenum aWhich, void ( CALLBACK* aFn )() );
void           gluTessProperty( GLUtesselator* aTess, GLenum aWhich, GLdouble aValue );
void           gluTessNormal( GLUtesselator* aTess, GLdouble aX, GLdouble aY, GLdouble aZ );
void           gluTessBeginPolygon( GLUtesselator* aTess, void* aData );
void           gluTessBeginContour( GLUtesselator* aTess );
void           gluTessVertex( GLUtesselator* aTess, GLdouble* aLocation, void* aData );
void           gluTessEndContour( GLUtesselator* aTess );
void           gluTessEndPolygon( GLUtesselator* aTess );
const unsigned char* gluErrorString( GLenum aError );

/* ---- Quadrics + perspective (implemented in glu_quadric_adapter.c) ---- */
typedef struct GLUquadric GLUquadric;
typedef GLUquadric GLUquadricObj;

typedef float GLfloat;
typedef int   GLint;

#define GLU_POINT          100010
#define GLU_LINE           100011
#define GLU_FILL           100012
#define GLU_SILHOUETTE     100013
#define GLU_SMOOTH         100000
#define GLU_FLAT           100001
#define GLU_NONE           100002
#define GLU_INSIDE         100020
#define GLU_OUTSIDE        100021

GLUquadricObj* gluNewQuadric( void );
void           gluDeleteQuadric( GLUquadricObj* q );
void           gluQuadricDrawStyle( GLUquadricObj* q, GLenum style );
void           gluQuadricNormals( GLUquadricObj* q, GLenum normals );
void           gluQuadricOrientation( GLUquadricObj* q, GLenum orientation );
void           gluQuadricTexture( GLUquadricObj* q, GLboolean texture );
void           gluQuadricCallback( GLUquadricObj* q, GLenum which, void (*fn)( void ) );
void           gluSphere( GLUquadricObj* q, GLdouble radius, GLint slices, GLint stacks );
void           gluCylinder( GLUquadricObj* q, GLdouble base, GLdouble top, GLdouble height,
                            GLint slices, GLint stacks );
void           gluDisk( GLUquadricObj* q, GLdouble inner, GLdouble outer, GLint slices,
                        GLint loops );
void           gluPartialDisk( GLUquadricObj* q, GLdouble inner, GLdouble outer, GLint slices,
                               GLint loops, GLdouble start, GLdouble sweep );
void           gluPerspective( GLdouble fovy, GLdouble aspect, GLdouble zNear, GLdouble zFar );

#ifdef __cplusplus
}
#endif

#endif /* KICAD_IOS_GLU_H */
