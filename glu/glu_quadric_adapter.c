/*
 * glu_quadric_adapter.c — GLU quadrics + gluPerspective for iOS, part
 * of the KiCad-IOS spike's GLU subset (see glu.h). GPL v3, same terms
 * as the rest of this repository.
 *
 * iOS has no GLU at all. KiCad's 3D viewer uses a small quadric
 * surface: gluNewQuadric / gluDeleteQuadric / gluQuadricNormals /
 * gluQuadricDrawStyle / gluSphere / gluCylinder / gluDisk, plus
 * gluPerspective for projection setup. The geometry here is the
 * classic GLU tessellation (UV sphere, open cylinder, flat annulus),
 * emitted as GL_TRIANGLES through KiCad's own glad function pointers
 * (glad_glBegin / glad_glVertex3d / ...), which is exactly how the
 * calling translation units reach GL themselves.
 *
 * Honest limits:
 *  - If the glad pointers are null (no legacy GL entry points exist
 *    under OpenGL ES — glBegin & friends simply do not exist there),
 *    the draw calls no-op instead of crashing. The affected visuals
 *    are the 3D viewer's navigation gizmo and measurement arrows:
 *    decorations, drawn by a renderer whose core pipeline does not
 *    depend on them.
 *  - Draw styles GLU_LINE / GLU_POINT / GLU_SILHOUETTE are accepted
 *    and rendered as GLU_FILL; KiCad only ever uses GLU_FILL.
 *  - Quadric texture generation is accepted but not emitted (KiCad
 *    never enables it).
 */

#include "glu.h"

#include <math.h>
#include <stdlib.h>

/* KiCad's glad loader pointers (thirdparty/glad, defined by the glad
 * translation unit in KiCad's own link closure). Declared here with
 * ABI-matching types; GLenum is unsigned int. */
extern void (*glad_glBegin)( unsigned int mode );
extern void (*glad_glEnd)( void );
extern void (*glad_glVertex3d)( double x, double y, double z );
extern void (*glad_glNormal3d)( double x, double y, double z );
extern void (*glad_glMultMatrixf)( const float* m );

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

/* GL_TRIANGLES */
#define ADPT_TRIANGLES 0x0004

struct GLUquadric
{
    GLenum drawStyle;
    GLenum normals;
    GLenum orientation;
    GLboolean texture;
};

GLUquadricObj* gluNewQuadric( void )
{
    GLUquadricObj* q = (GLUquadricObj*) calloc( 1, sizeof( GLUquadricObj ) );

    if( q )
    {
        q->drawStyle = GLU_FILL;
        q->normals = GLU_SMOOTH;
        q->orientation = GLU_OUTSIDE;
        q->texture = 0;
    }

    return q;
}

void gluDeleteQuadric( GLUquadricObj* q )
{
    free( q );
}

void gluQuadricDrawStyle( GLUquadricObj* q, GLenum style )
{
    if( q )
        q->drawStyle = style;
}

void gluQuadricNormals( GLUquadricObj* q, GLenum normals )
{
    if( q )
        q->normals = normals;
}

void gluQuadricOrientation( GLUquadricObj* q, GLenum orientation )
{
    if( q )
        q->orientation = orientation;
}

void gluQuadricTexture( GLUquadricObj* q, GLboolean texture )
{
    if( q )
        q->texture = texture;
}

void gluQuadricCallback( GLUquadricObj* q, GLenum which, void (*fn)( void ) )
{
    (void) q; (void) which; (void) fn; /* accepted, never invoked */
}

static int gl_ready( void )
{
    return glad_glBegin && glad_glEnd && glad_glVertex3d;
}

static void emit_vertex( const GLUquadricObj* q, double nx, double ny, double nz,
                         double x, double y, double z )
{
    if( q->normals != GLU_NONE && glad_glNormal3d )
    {
        double s = ( q->orientation == GLU_INSIDE ) ? -1.0 : 1.0;
        glad_glNormal3d( s * nx, s * ny, s * nz );
    }

    glad_glVertex3d( x, y, z );
}

static void emit_tri( const GLUquadricObj* q, const double a[3], const double b[3],
                      const double c[3], const double na[3], const double nb[3],
                      const double nc[3] )
{
    /* Winding flips for GLU_INSIDE so face orientation stays outward
     * relative to the (flipped) normals. */
    if( q->orientation == GLU_INSIDE )
    {
        emit_vertex( q, na[0], na[1], na[2], a[0], a[1], a[2] );
        emit_vertex( q, nc[0], nc[1], nc[2], c[0], c[1], c[2] );
        emit_vertex( q, nb[0], nb[1], nb[2], b[0], b[1], b[2] );
    }
    else
    {
        emit_vertex( q, na[0], na[1], na[2], a[0], a[1], a[2] );
        emit_vertex( q, nb[0], nb[1], nb[2], b[0], b[1], b[2] );
        emit_vertex( q, nc[0], nc[1], nc[2], c[0], c[1], c[2] );
    }
}

void gluSphere( GLUquadricObj* q, GLdouble radius, GLint slices, GLint stacks )
{
    if( !q || radius <= 0 || slices < 2 || stacks < 1 || !gl_ready() )
        return;

    glad_glBegin( ADPT_TRIANGLES );

    for( int j = 0; j < stacks; j++ )
    {
        double p0 = M_PI * (double) j / stacks;         /* phi, from +Z */
        double p1 = M_PI * (double) ( j + 1 ) / stacks;

        for( int i = 0; i < slices; i++ )
        {
            double t0 = 2.0 * M_PI * (double) i / slices;
            double t1 = 2.0 * M_PI * (double) ( i + 1 ) / slices;
            double v[4][3], n[4][3];
            const double ph[2] = { p0, p1 };
            const double th[2] = { t0, t1 };
            int k = 0;

            for( int a = 0; a < 2; a++ )
            {
                for( int b = 0; b < 2; b++, k++ )
                {
                    double sp = sin( ph[a] ), cp = cos( ph[a] );
                    v[k][0] = radius * sp * cos( th[b] );
                    v[k][1] = radius * sp * sin( th[b] );
                    v[k][2] = radius * cp;
                    n[k][0] = v[k][0] / radius;
                    n[k][1] = v[k][1] / radius;
                    n[k][2] = v[k][2] / radius;
                }
            }
            /* v: [0]=(p0,t0) [1]=(p0,t1) [2]=(p1,t0) [3]=(p1,t1) */
            emit_tri( q, v[0], v[2], v[3], n[0], n[2], n[3] );
            emit_tri( q, v[0], v[3], v[1], n[0], n[3], n[1] );
        }
    }

    glad_glEnd();
}

void gluCylinder( GLUquadricObj* q, GLdouble base, GLdouble top, GLdouble height,
                  GLint slices, GLint stacks )
{
    if( !q || height <= 0 || slices < 2 || stacks < 1 || !gl_ready() )
        return;

    glad_glBegin( ADPT_TRIANGLES );

    for( int j = 0; j < stacks; j++ )
    {
        double z0 = height * (double) j / stacks;
        double z1 = height * (double) ( j + 1 ) / stacks;
        double r0 = base + ( top - base ) * (double) j / stacks;
        double r1 = base + ( top - base ) * (double) ( j + 1 ) / stacks;
        /* Side normal tilt from the cone slope. */
        double slope = ( base - top ) / height;

        for( int i = 0; i < slices; i++ )
        {
            double t0 = 2.0 * M_PI * (double) i / slices;
            double t1 = 2.0 * M_PI * (double) ( i + 1 ) / slices;
            double c0 = cos( t0 ), s0 = sin( t0 ), c1 = cos( t1 ), s1 = sin( t1 );
            double il = 1.0 / sqrt( 1.0 + slope * slope );
            double v00[3] = { r0 * c0, r0 * s0, z0 }, v01[3] = { r0 * c1, r0 * s1, z0 };
            double v10[3] = { r1 * c0, r1 * s0, z1 }, v11[3] = { r1 * c1, r1 * s1, z1 };
            double n0[3] = { c0 * il, s0 * il, slope * il };
            double n1[3] = { c1 * il, s1 * il, slope * il };

            emit_tri( q, v00, v10, v11, n0, n0, n1 );
            emit_tri( q, v00, v11, v01, n0, n1, n1 );
        }
    }

    glad_glEnd();
}

void gluDisk( GLUquadricObj* q, GLdouble inner, GLdouble outer, GLint slices, GLint loops )
{
    if( !q || outer <= 0 || slices < 2 || loops < 1 || !gl_ready() )
        return;

    const double nz = 1.0;

    glad_glBegin( ADPT_TRIANGLES );

    for( int j = 0; j < loops; j++ )
    {
        double r0 = inner + ( outer - inner ) * (double) j / loops;
        double r1 = inner + ( outer - inner ) * (double) ( j + 1 ) / loops;

        for( int i = 0; i < slices; i++ )
        {
            double t0 = 2.0 * M_PI * (double) i / slices;
            double t1 = 2.0 * M_PI * (double) ( i + 1 ) / slices;
            double v00[3] = { r0 * cos( t0 ), r0 * sin( t0 ), 0.0 };
            double v01[3] = { r0 * cos( t1 ), r0 * sin( t1 ), 0.0 };
            double v10[3] = { r1 * cos( t0 ), r1 * sin( t0 ), 0.0 };
            double v11[3] = { r1 * cos( t1 ), r1 * sin( t1 ), 0.0 };
            double n[3] = { 0.0, 0.0, nz };

            emit_tri( q, v00, v10, v11, n, n, n );
            emit_tri( q, v00, v11, v01, n, n, n );
        }
    }

    glad_glEnd();
}

void gluPartialDisk( GLUquadricObj* q, GLdouble inner, GLdouble outer, GLint slices,
                     GLint loops, GLdouble start, GLdouble sweep )
{
    (void) start; (void) sweep; /* KiCad never calls this; full disk is
                                   the honest fallback if it ever does. */
    gluDisk( q, inner, outer, slices, loops );
}

void gluPerspective( GLdouble fovy, GLdouble aspect, GLdouble zNear, GLdouble zFar )
{
    if( !glad_glMultMatrixf || zNear <= 0 || zFar <= zNear || aspect == 0 )
        return;

    double f = 1.0 / tan( fovy * M_PI / 360.0 );
    float m[16] = { 0 };

    m[0] = (float) ( f / aspect );
    m[5] = (float) f;
    m[10] = (float) ( ( zFar + zNear ) / ( zNear - zFar ) );
    m[11] = -1.0f;
    m[14] = (float) ( 2.0 * zFar * zNear / ( zNear - zFar ) );

    glad_glMultMatrixf( m );
}
